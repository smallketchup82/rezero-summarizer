import argparse
import openai
import tqdm
import tiktoken
from distutils.util import strtobool
import time
import os
import warnings
import re
from version import __version__
from colorama import Fore, Back, Style, init
init(autoreset=True)

from dotenv import load_dotenv
load_dotenv()

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

parser = argparse.ArgumentParser(prog="sumzero", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
parser.add_argument("-c", "--chapter", type=str, help="Chapter to summarize. Leave blank to summarize all chapters.", default=None)
parser.add_argument("-i", "--input", type=str, help="The path to the .txt file of the arc. Required", required=True)
parser.add_argument("-o", "--output", type=str, help="Output folder path", default="output")
parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
parser.add_argument("--dump", help="Dump the entire processed text into a file", action="store_true")
parser.add_argument("-f", "--force", help="Overwrite the output file if it already exists", action="store_true")
parser.add_argument("-s", "--skip", help="Skip the countdown (Not recommended)", action="store_true")
parser.add_argument("--dry-run", help="Don't actually summarize anything", action="store_true")
parser.add_argument("--api-key", type=str, help="OpenAI API key. If not specified, will use the OPENAI_API_KEY environment variable", default=None)
parser.add_argument("--org", type=str, help="OpenAI organization. If not specified, will use the OPENAI_ORG environment variable", default=None)
parser.add_argument("-t", "--temperture", type=float, help="The temperature to use for the API call. Default is recommened but tune it as you wish", default=0.0)
args = parser.parse_args()

openai.api_key = args.api_key or os.getenv("OPENAI_API_KEY")
openai.organization = args.org or os.getenv("OPENAI_ORG")

if not "7" in args.input:
    print("This script is meant to summarize Arc 7. Are you sure you want to continue?")
    if not strtobool(input("Continue? (y/n): ")):
        exit()

outputdir = os.path.abspath(args.output) if args.output else os.path.join(os.getcwd(), "output")
os.makedirs(outputdir, exist_ok=True)

file = open(args.input, "r", encoding="utf-8")
text = file.read()

# TODO: Make this work for all arcs (currently only works for Arc 7)
text = re.sub(r"^.*?(?=Arc 7 Chapter 1 – Initiation).+(?=Arc 7 Chapter 1 – Initiation)", "", text, flags=re.S | re.I) # Remove the table of contents
texts = re.split(r"(?=Arc 7 Chapter \w.*$)|△▼△▼△▼△|※　※　※　※　※　※　※　※　※　※　※　※　※", text, flags=re.M | re.I) # Split the text into chapters and parts
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
        texts[i] = re.sub(r"(Arc 7 Chapter \w+ – [^\n\r]*\n?)(.* ― Complete\n?)", r"\1", texts[i], flags=re.S | re.I)
        
# Dump the processed text into a file if requested, for debugging purposes
if args.dump:
    with open(os.path.join(outputdir, "Arc 7 Processed.txt"), "w", encoding="utf-8") as file:
        file.write("\n\n".join(texts))
        print("Dumped processed text to file")
        exit()

if not args.skip:
    print("Starting summarization in 5 seconds...\nPlease terminate now (Ctrl+C) if unintended.")
    time.sleep(5)

# Summarizer process
def summarize(i):
    prompt = "\n<END>\n\nCreate a comprehensive plot synopsis of this part of a chapter from a book.\nMake your plot synopsis as lengthy and detailed as possible."
    total = texts[i] + prompt
    tokens = len(enc.encode(total))
    
    if tokens < 3097:
        model = "gpt-3.5-turbo"
        max_tokens = 1000
    elif tokens < 14385:
        model = "gpt-3.5-turbo-16k"
        max_tokens = 2000
    else:
        warnings.warn(f"Index {str(i)} is too long. Skipping...")
    
    print(Fore.CYAN + "\n" + texts[i].split("\n")[0].center(os.get_terminal_size().columns)) # Print the chapter title
    print(Fore.CYAN + f"Index: {i} | Model: {model} | Tokens: {tokens} | Words: {len(total.split())} | Characters: {len(total)}\n".center(os.get_terminal_size().columns)) # Print info
    
    try:
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
    except Exception as e:
        raise Exception(f"Error at index {i}: {e}")
    
    summary = APIsummary['choices'][0]['message']['content']
    if summary == "":
        warnings.warn(f"Summary for index {str(i)} is empty!")
    return summary

# Handle individual chapters
def handleIndividualChapter(chapter):
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


# If the user specified a chapter, handle that chapter. Otherwise, summarize all chapters.
if args.chapter:
    chapters = str(args.chapter).split(",")
    print(Fore.YELLOW + "[-] " + "Handling chapter(s) " + ", ".join(chapters))
    
    for chapter in chapters:
        print(Fore.YELLOW + "\n[-] " + "Processing chapter " + chapter + "...")
        handleIndividualChapter(chapter.strip())
        print(Fore.GREEN + "[✓] " + "Processed chapter " + chapter + "!")
    
    print(Fore.GREEN + "[✓] " + "Done!")
else:
    if args.force and os.path.exists(os.path.join(outputdir, "Summary.txt")):
        os.remove(os.path.join(outputdir, "Summary.txt"))
        
    for i in tqdm.trange(len(texts)):
        summary = summarize(i) if not args.dry_run else "Dry run"
        
        if args.verbose:
            print('\n------------------------------------------------\nSummary:')
            print(summary)
            print("------------------------------------------------")
            
        with open(os.path.join(outputdir, "Summary.txt"), "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open(os.path.join(outputdir, "Summary.txt"), "r+", encoding="utf-8") as file:
        fart = file.read()
        fart = fart.strip()
        file.seek(0)
        file.write(fart)
        file.truncate()
        file.close()