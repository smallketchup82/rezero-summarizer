import argparse
import openai
import tqdm
import tiktoken
from distutils.util import strtobool
import time
import os
import warnings
import shutil
import re
from version import __version__
import questionary
from colorama import Fore, Back, Style, init
from tenacity import retry, stop_after_delay, wait_random_exponential
init(autoreset=True)

from dotenv import load_dotenv
load_dotenv()

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

parser = argparse.ArgumentParser(prog="sumzero", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
parser.add_argument("-m", "--merge", help="Merge all of the outputs into a single file", action="store_true")
parser.add_argument("-i", "--input", type=str, help="The path to the .txt file of the arc. Required", required=True)
parser.add_argument("-o", "--output", type=str, help="Output folder path", default="output")
parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
parser.add_argument("--dump", help="Dump the entire processed text into a file", action="store_true")
parser.add_argument("-f", "--force", help="Overwrite the output file if it already exists", action="store_true")
parser.add_argument("--dry-run", help="Don't actually summarize anything", action="store_true")
parser.add_argument("--api-key", type=str, help="OpenAI API key. If not specified, will use the OPENAI_API_KEY environment variable", default=None)
parser.add_argument("--org", type=str, help="OpenAI organization. If not specified, will use the OPENAI_ORG environment variable", default=None)
parser.add_argument("-t", "--temperature", type=float, help="The temperature to use for the API call. Default is recommened but tune it as you wish", default=0.0)
parser.add_argument("--gpt4", help="Use GPT-4-Turbo (warning very expensive)", action="store_true")
args = parser.parse_args()

openai.api_key = args.api_key or os.getenv("OPENAI_API_KEY")
openai.organization = args.org or os.getenv("OPENAI_ORG")

outputdir = os.path.abspath(args.output) if args.output else os.path.join(os.getcwd(), "output")
if args.merge:
    originaloutputdir = outputdir
    outputdir = os.path.join(outputdir, "temp")
os.makedirs(outputdir, exist_ok=True)

file = open(args.input, "r", encoding="utf-8")
text = file.read()

arcnumber = re.search(r"(?<=Arc )\d+", text).group(0) # Looks for the first reference of the arc and the number, and assumes that this is the arc number

# Split the whole arc into chapters and parts
text = re.sub(r"^.*?(?=Arc .+ Chapter 1 –).+(?=Arc .+ Chapter 1 –)", "", text, flags=re.S | re.I) # Remove the table of contents by finding fist entry in TOC and removing until that chapter starts
texts = re.split(r"(?=Arc .+ Chapter \w.*$)|△▼△▼△▼△|※　※　※　※　※　※　※　※　※　※　※　※　※", text, flags=re.M | re.I) # Split the text into chapters and parts
texts = list(filter(None, texts)) # Remove empty strings from the list

# Remove illustration captions
for i in range(len(texts)):
    texts[i] = re.sub("Illustration from Volume.*$", "", texts[i], flags=re.M | re.I)

# Remove whitespace
for i in range(len(texts)):
    texts[i] = texts[i].strip()

# Remove unncessary spaces
for i in range(len(texts)):
    texts[i] = re.sub(r" +", " ", texts[i])

# Remove unnecessary newlines
for i in range(len(texts)):
    texts[i] = re.sub(r"\n+", "\n", texts[i])
    
# Every chapter has a title in the first line of the text. However, the parts do not have such a title.
# Iterate through the texts and add a title to the first line of each part, incrementing the part number each time until the next time we encounter a chapter title (e.g. "Chapter 2 Part 1").
part = 1
chapter = "0"
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    
    if "Chapter" in firstline and not "Part" in firstline:
        part = 1
        chapter = str(re.search(r"(?<=Chapter )\w+", firstline).group(0))
        
    if not "Chapter" in firstline:
        part += 1
        texts[i] = f"Chapter {chapter} Part {part}\n{texts[i]}"

# Remove info proceeding the chapter title
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    if "Chapter" in firstline:
        texts[i] = re.sub(r"(Arc .* Chapter \w+ – [^\n\r]*\n?)(.* ― Complete\n?)", r"\1", texts[i], flags=re.S | re.I)
        
# Dump the processed text into a file if requested, for debugging purposes
if args.dump:
    with open(os.path.join(outputdir, f"Arc {arcnumber} Processed.txt"), "w", encoding="utf-8") as file:
        file.write("\n\n".join(texts))
        print("Dumped processed text to file")
        exit()

def summarize(i):
    """Summarizer process. Not meant to be called directly.

    Args:
        i (int): The index of the part of the chapter to summarize
    """
    prompt = "\n<END>\n\nCreate a comprehensive plot synopsis of this part of a chapter from a book.\nMake your plot synopsis as lengthy and detailed as possible."
    total = texts[i] + prompt
    tokens = len(enc.encode(total))
    
    if args.gpt4 and tokens < 124000:
        model = "gpt-4-1106-preview"
        max_tokens = 4000
    elif tokens < 14385:
        model = "gpt-3.5-turbo-1106"
        max_tokens = 2000
    else:
        raise Exception(f"Index {str(i)} is too long")
    
    print(Fore.CYAN + "\n" + texts[i].split("\n")[0].center(os.get_terminal_size().columns)) # Print the chapter title
    print(Fore.CYAN + f"Index: {i} | Model: {model} | Tokens: {tokens} | Words: {len(total.split())} | Characters: {len(total)}\n".center(os.get_terminal_size().columns)) # Print info
    
    # Retry if the API call fails. Will exponentially backoff and retry until 1 minute has passed. Then it will randomly backoff and retry until 5 minutes have passed. To which it will then give up and reraise the exception.
    @retry (stop=stop_after_delay(300), wait=wait_random_exponential(multiplier=1, min=1, max=10), reraise=True)
    def sendRequest():
        APIsummary = openai.ChatCompletion.create(
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
    
    summary = sendRequest()['choices'][0]['message']['content']
    if summary == "":
        warnings.warn(f"Summary for index {str(i)} is empty!")
    return summary

def handleIndividualChapter(chapter):
    """Handler for individual chapters

    Args:
        chapter (str | int): Index of the chapter to summarize
    """
    actualchapter = None
    indices = []
    
    print(Fore.YELLOW + "[-] " + "Searching for chapter...")
    for i in range(len(texts)):
        if f"Chapter {chapter} " in texts[i]:
            indices.append(i)
        else:
            continue
    
    if indices == []:
        raise Exception("Chapter not found")
    
    actualchapter = indices[0]
    
    print(Fore.GREEN + "[✓] " + f"Found Chapter {chapter} at Index {actualchapter}!")
    
    if args.force and os.path.exists(os.path.join(outputdir, f"Chapter {chapter} Summary.txt")):
        os.remove(os.path.join(outputdir, f"Chapter {chapter} Summary.txt"))
    elif os.path.exists(os.path.join(outputdir, f"Chapter {chapter} Summary.txt")):
        warnings.warn(f"Chapter {chapter} Summary.txt already exists. Will append to the file!")
    
    print(Fore.YELLOW + "[-] " + "Summarizing...")
    print("-" * os.get_terminal_size().columns)
    
    for i in tqdm.trange(len(indices), unit="part"):
        i = indices[i]
        if not args.dry_run:
            summary = summarize(i)
        else:
            summary = "Dry run"
            time.sleep(1)
        
        if args.verbose:
            print(Fore.GREEN + 'Summary'.center(os.get_terminal_size().columns))
            print(summary)
            print(Fore.CYAN + f"Words: {len(summary.split())} | Characters: {len(summary)}".center(os.get_terminal_size().columns))
            print("-" * os.get_terminal_size().columns)
        
        # Write to file
        with open(os.path.join(outputdir, f"Chapter {chapter} Summary.txt"), "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open(os.path.join(outputdir, f"Chapter {chapter} Summary.txt"), "r+", encoding="utf-8") as file:
        fart = file.read()
        fart = fart.strip()
        file.seek(0)
        file.write(fart)
        file.truncate()
        file.close()

chaptersinarc = []

# Get all chapters in the arc and add them to a list
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    
    if "Chapter" in firstline and not "Part" in firstline:
        chaptersinarc.append(firstline)

# Ask the user which chapters they want to summarize
chapters: list | None = questionary.checkbox(
    "Which chapter(s) do you want to summarize?",
    choices=chaptersinarc,
).ask()

if chapters == None or chapters == []:
    print("No chapters selected. Exiting...")
    exit()

# Get the chapter number from the chapter title
for i in range(len(chapters)):
    chapters[i] = str(re.search(r"(?<=Chapter )\w+", chapters[i]).group(0))

# Sort the chapters in ascending order
chapters.sort()

print(Fore.YELLOW + "[-] " + "Handling chapter(s) " + ", ".join(chapters))

if args.merge:
    # Remove the temp folder if it already exists
    if os.path.exists(outputdir):
        shutil.rmtree(outputdir)
        os.mkdir(outputdir)
        

# Handle each chapter
for chapter in chapters:
    print(Fore.YELLOW + "\n[-] " + "Processing chapter " + chapter + "...")
    handleIndividualChapter(chapter.strip())
    print(Fore.GREEN + "[✓] " + "Processed chapter " + chapter + "!")

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
            with open(os.path.join(outputdir, f"Chapter {chapter} Summary.txt"), "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n\n")
                infile.close()
        outfile.close()
        
    # Delete the temp folder
    shutil.rmtree(outputdir)
    
    print(Fore.GREEN + "[✓] " + "Merged files!")

print(Fore.GREEN + "[✓] " + "Done!")