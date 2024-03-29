import argparse
import gc
import os
import re
import shutil
import time
import warnings

import questionary
import tiktoken
import tqdm
from colorama import Fore, init
from openai import OpenAI
from tenacity import retry, stop_after_delay, wait_random_exponential

from version import __version__

init(autoreset=True)

from dotenv import load_dotenv

load_dotenv()

print = tqdm.tqdm.write
enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

parser = argparse.ArgumentParser(prog="sum:zero", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-V", "--version", action="version", version=f"{__version__}")
parser.add_argument("-c", "--chapter", type=str, help="Chapters to summarize. Use a comma-separated list for multiple chapters", default=None)
parser.add_argument("-m", "--merge", help="Merge all of the outputs into a single file", action="store_true")
parser.add_argument("-i", "--input", type=str, help="The path to the .txt file of the arc. Required", required=True)
parser.add_argument("-o", "--output", type=str, help="Output folder path", default="output")
parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
parser.add_argument("--dump", help="Dump the entire processed text into a file", action="store_true")
parser.add_argument("--dry-run", help="Don't actually summarize anything", action="store_true")
parser.add_argument("--api-key", type=str, help="OpenAI API key. If not specified, will use the OPENAI_API_KEY environment variable", default=None)
parser.add_argument("--org", type=str, help="OpenAI organization. If not specified, will use the OPENAI_ORG environment variable", default=None)
parser.add_argument("-t", "--temperature", type=float, help="The temperature to use for the API call. Default is recommened but tune it as you wish", default=0.0)
parser.add_argument("--gpt4", help="Use GPT-4-Turbo (warning very expensive)", action="store_true")
parser.add_argument("-O", "--open", help="Open the generated summary if you only summarized one chapter or merged outputs. Otherwise, open the output folder.", action="store_true")
args = parser.parse_args()

openai_client = OpenAI(
    api_key=args.api_key or os.getenv("OPENAI_API_KEY"),
    organization=args.org or os.getenv("OPENAI_ORG")
)

outputdir = os.path.abspath(args.output) if args.output else os.path.join(os.getcwd(), "output")
if args.merge:
    originaloutputdir = outputdir
    outputdir = os.path.join(outputdir, "temp")
os.makedirs(outputdir, exist_ok=True)

file = open(args.input, "r", encoding="utf-8")
text = file.read()

arcnumber = re.search(r"(?<=Arc )\d+", text).group(0) # Looks for the first reference of the arc and the number, and assumes that this is the arc number
if arcnumber is None:
    raise Exception("Arc number could not be found!")

# Split the whole arc into chapters and parts
text = re.sub(fr"^.*?(?=Arc {arcnumber} Chapter 1 –).+(?=Arc {arcnumber} Chapter 1 –)", "", text, flags=re.S | re.I) # Remove the table of contents by finding the first entry in TOC and removing until that chapter starts
text = re.sub(r"Other Volumes.*", "", text, flags=re.S | re.I)
texts = re.split(fr"(?=Arc {arcnumber} Chapter \w.*$)|△▼△▼△▼△|※　※　※　※　※　※　※　※　※　※　※　※　※", text, flags=re.M | re.I) # Split the text into chapters and parts
texts = list(filter(None, texts)) # Remove empty strings from the list

# Process the text
for i in range(len(texts)):
    texts[i] = re.sub("Illustration from Volume.*$", "", texts[i], flags=re.M | re.I) # Remove illustration captions
    texts[i] = re.sub("Character Pages.*$", "", texts[i], flags=re.M | re.I) # Remove Character Page titles
    texts[i] = re.sub("Web Novel Volume.*$", "", texts[i], flags=re.M | re.I) # Remove Volume titles
    texts[i] = texts[i].strip() # Remove whitespace
    texts[i] = re.sub(r" +", " ", texts[i]) # Remove unncessary spaces
    texts[i] = re.sub(r"\n+", "\n", texts[i]) # Remove unnecessary newlines
    
# Every chapter has a title in the first line of the text. However, the parts do not have such a title.
# Iterate through the texts and add a title to the first line of each part, incrementing the part number each time until the next time we encounter a chapter title (e.g. "Chapter 2 Part 1").
part = 1
chapter = "0"
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    
    if "Chapter" in firstline and "Part" not in firstline:
        part = 1
        chapter = str(re.search(r"(?<=Chapter )\w+", firstline).group(0))
        
    if "Chapter" not in firstline:
        part += 1
        texts[i] = f"Chapter {chapter} Part {part}\n{texts[i]}"

# Remove info proceeding the chapter title
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    if "Chapter" in firstline:
        texts[i] = re.sub(fr"(Arc {arcnumber} Chapter \w+ – [^\n\r]*\n?)(.* ― Complete\n?)", r"\1", texts[i], flags=re.S | re.I)
        
# Dump the processed text into a file if requested, for debugging purposes
if args.dump:
    with open(os.path.join(outputdir, f"Arc {arcnumber} Processed.txt"), "w", encoding="utf-8") as file:
        file.write("\n\n".join(texts))
        print("Dumped processed text to file")
        exit()

def summarize(i: int) -> str:
    """Summarizer process. Not meant to be called directly.

    Args:
        i (int): The index of the part of the chapter to summarize
    """
    prompt = "\n<END>\n\nCreate a comprehensive plot synopsis of this part of a chapter from a book.\nMake your plot synopsis as lengthy and detailed as possible."
    total = texts[i] + prompt
    tokens = len(enc.encode(total))
    
    if args.gpt4 and tokens < 124000:
        model = "gpt-4-0125-preview"
        max_tokens = 4000
    elif tokens < 14385:
        model = "gpt-3.5-turbo-0125"
        max_tokens = 2000
    else:
        raise Exception(f"Index {str(i)} is too long")
    
    if args.verbose:
        print(Fore.CYAN + "\n" + texts[i].split("\n")[0].center(os.get_terminal_size().columns)) # Print the chapter title
        print(Fore.CYAN + f"Index: {i} | Model: {model} | Tokens: {tokens} | Words: {len(total.split())} | Characters: {len(total)}\n".center(os.get_terminal_size().columns)) # Print info
    
    if args.dry_run:
        time.sleep(1)
        return "Dry run"
    
    # Retry if the API call fails. Will exponentially backoff and retry until 1 minute has passed. Then it will randomly backoff and retry until 5 minutes have passed. To which it will then give up and reraise the exception.
    @retry (stop=stop_after_delay(300), wait=wait_random_exponential(multiplier=1, min=1, max=10), reraise=True)
    def sendRequest():
        APIsummary = openai_client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=args.temperature,
            messages=[
                {
                    "role": "user",
                    "content": f"{texts[i]}{prompt}"
                }
            ]
        )
        
        return APIsummary
    
    summary = sendRequest().choices[0].message.content
    if summary == "" or summary is None:
        warnings.warn(f"Summary for index {str(i)} is empty!")
    return summary

def handleIndividualChapter(chapter: str | int) -> None:
    """Handler for individual chapters

    Args:
        chapter (str | int): Index of the chapter to summarize
    """
    indices = []
    
    for i in range(len(texts)):
        if f"Chapter {chapter} " in texts[i]:
            indices.append(i)
        else:
            continue
    
    if indices == []:
        raise Exception("Chapter not found")
    
    print(Fore.YELLOW + "[-] " + "Summarizing...")
    
    fullsummary: str = ""
    
    for i in tqdm.trange(len(indices), unit="part", desc=f"Chapter {chapter}", leave=False):
        i = indices[i]
        summary = summarize(i)
        
        if args.verbose:
            print(Fore.GREEN + 'Summary'.center(os.get_terminal_size().columns))
            print(summary)
            print(Fore.CYAN + f"Words: {len(summary.split())} | Characters: {len(summary)}".center(os.get_terminal_size().columns))
            print("-" * os.get_terminal_size().columns)
        
            
        # Append to the summary variable
        firstline: str = texts[i].split("\n")[0]
        fullsummary += f"{firstline}\n{summary}\n\n\n"
            
    # Write to file
    with open(os.path.join(outputdir, f"Arc {arcnumber} Chapter {chapter} Summary.txt"), "w+", encoding="utf-8") as file:
        file.write(fullsummary)
        file.seek(0)
        fart = file.read()
        fart = fart.strip()
        file.seek(0)
        file.write(fart)
        file.truncate()
        file.close()
        
    # Manually trigger garbage collection since this is a good time to do so
    print(Fore.YELLOW + "[-] Garbage collecting...")
    gc.collect()
    
chaptersinarc = []

# Get all chapters in the arc and add them to a list
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    
    if "Chapter" in firstline and "Part" not in firstline:
        chaptersinarc.append(firstline)

# If the user specified a chapter, use that instead of asking them
if args.chapter:
    # remove whitespace and split the string into a list
    chapters: list = args.chapter.replace(" ", "").split(",")

    if chapters is None or chapters == []:
        print("No chapters selected. Exiting...")
        exit()
else:
    # Ask the user which chapters they want to summarize
    chapters: list | None = questionary.checkbox(
        "Which chapter(s) do you want to summarize?",
        choices=chaptersinarc,
    ).ask()

    if chapters is None or chapters == []:
        print("No chapters selected. Exiting...")
        exit()

    # Get the chapter number from the chapter title
    for i in range(len(chapters)):
        chapters[i] = str(re.search(r"(?<=Chapter )\w+", chapters[i]).group(0))
    
if args.gpt4:
    warnings.warn("Using GPT-4-Turbo. Be warned that this is very expensive.")

# Sort the chapters in ascending order
chapters.sort()

print(Fore.YELLOW + "[-] " + "Handling chapter(s): " + ", ".join(chapters))

if args.merge:
    # Remove the temp folder if it already exists
    if os.path.exists(outputdir):
        shutil.rmtree(outputdir)
        os.mkdir(outputdir)
        

# Handle each chapter
for chapter in tqdm.tqdm(chapters, desc="Total progress", unit="chapter", leave=False):
    print("-" * os.get_terminal_size().columns)
    print(Fore.YELLOW + "[-] " + "Processing chapter " + chapter + "...")
    handleIndividualChapter(chapter.strip())
    print(Fore.GREEN + "[✓] " + "Processed chapter " + chapter + "!")

if args.open and len(chapters) == 1 and not args.merge:
    os.startfile(os.path.join(outputdir, f"Arc {arcnumber} Chapter {chapter} Summary.txt"))
elif args.open and not args.merge:
    os.startfile(outputdir)

# Format the chapter range
# e.g. [1, 2, 3, 4, 5, 6, 7, 8, 9] -> "1-9"
# e.g. [1, 2, 3, 4, 5, 6, 7, 8, 10] -> "1...10"
def format_chapter_range(chapters):
    chapters = sorted(chapters, key=int)
    prev = int(chapters[0])
    for chapter in chapters[1:]:
        if int(chapter) != prev + 1:
            return f"{chapters[0]}...{chapters[-1]}"
        prev = int(chapter)
    return f"{chapters[0]}-{chapters[-1]}"
    
# Merge all of the files into a single file
if args.merge:
    print(Fore.YELLOW + "\n[-] " + "Merging files...")
    with open(os.path.join(originaloutputdir, f"Arc {arcnumber} Chapter(s) {format_chapter_range(chapters)} Summary.txt"), "w", encoding="utf-8") as outfile:
        for chapter in chapters:
            with open(os.path.join(outputdir, f"Arc {arcnumber} Chapter {chapter} Summary.txt"), "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n\n")
                infile.close()
        outfile.close()
    
    if args.open:
        os.startfile(os.path.join(outputdir, f"Arc {arcnumber} Chapter {chapter} Summary.txt"))
        
    # Delete the temp folder
    shutil.rmtree(outputdir)
    
    print(Fore.GREEN + "[✓] " + "Merged files!")

print(Fore.GREEN + "[✓] " + "Done!")