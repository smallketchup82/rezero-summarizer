import argparse
import openai
import tqdm
import tiktoken
from distutils.util import strtobool
import time
import os
import warnings
enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

from dotenv import load_dotenv
load_dotenv()

import re

openai.api_key = os.getenv("OPENAI_API_KEY")
openai.organization = os.getenv("OPENAI_ORG")

parser = argparse.ArgumentParser(description='AI Re:Zero Web Novel Summarizer', prog="sumzero")
parser.add_argument("-c", "--chapter", type=str, help="Chapter to summarize. Leave blank to summarize all chapters.", default=None)
parser.add_argument("-o", "--output", type=str, help="Output file path. Defaults to Summary.txt", default="Summary.txt")
parser.add_argument("-v", "--verbose", help="Verbose mode. Defaults to true", action="store_true")
parser.add_argument("--dump", help="Dump the entire processed text into a file. Defaults to false", action="store_true")
parser.add_argument("-f", "--force", help="Overwrite the output file if it already exists. Defaults to false", action="store_true")
parser.add_argument("-s", "--skip", help="Skip the countdown (Not recommended)", action="store_true")
args = parser.parse_args()

file = open("Arc 7.txt", "r", encoding="utf-8")
text = file.read()
text = re.sub(r"^.*?(?=Arc 7 Chapter 1 – Initiation).+(?=Arc 7 Chapter 1 – Initiation)", "", text, flags=re.S | re.I) # Remove the table of contents
texts = re.split(r"(?=Arc 7 Chapter \w.*$)|△▼△▼△▼△", text, flags=re.M | re.I) # Split the text into chapters and parts
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
        

if args.dump:
    with open("Arc 7 processed.txt", "w", encoding="utf-8") as file:
        file.write("\n\n".join(texts))
        print("Dumped processed text to file")
        exit()

if not args.skip:
    print("Starting summarization in 5 seconds...")
    time.sleep(5)

# Summarize process
def summarize(i):
    prompt = "\n<END>\n\nCreate a comprehensive plot synopsis of this part of a chapter from a book.\nMake your plot synopsis as lengthy and detailed as possible."
    tokens = len(enc.encode(texts[i])) + len(enc.encode(prompt))
    total = texts[i] + prompt
    
    if tokens < 3097:
        model = "gpt-3.5-turbo"
        max_tokens = 1000
    elif tokens < 14385:
        model = "gpt-3.5-turbo-16k"
        max_tokens = 2000
    else:
        warnings.warn(f"Index {str(i)} is too long. Skipping...")
    
    print("\n" + texts[i].split("\n")[0]) # Print the chapter title
    print(f"Index: {i} | Model: {model} | Tokens: {tokens} | Words: {len(total.split())} | Characters: {len(total)}\n") # Print info
    
    try:
        APIsummary = openai.ChatCompletion.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
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
    
    print("Searching for chapter...")
    for i in tqdm.trange(len(texts)):
        if f"Chapter {chapter} " in texts[i]:
            indices.append(i)
        else:
            continue
    
    if indices == []:
        raise Exception("Chapter not found")
    
    actualchapter = indices[0]
    
    print(f"Found Chapter {chapter} at Index {actualchapter}")
    
    if args.force and os.path.exists(f"./Chapter {chapter} Summary.txt"):
        os.remove(f"./Chapter {chapter} Summary.txt")
    
    for i in tqdm.trange(len(indices)):
        i = indices[i]
        summary = summarize(i)
        
        if args.verbose:
            print('------------------------------------------------\nSummary')
            print(summary)
            print(f"Words: {len(summary.split())} | Characters: {len(summary)}")
            print("------------------------------------------------")
        
        # Write to file
        with open(f"Chapter {chapter} Summary.txt", "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open(f"Chapter {chapter} Summary.txt", "r+", encoding="utf-8") as file:
        fart = file.read()
        fart = fart.strip()
        file.seek(0)
        file.write(fart)
        file.truncate()
        file.close()


# If the user specified a chapter, handle that chapter. Otherwise, summarize all chapters.
if args.chapter:
    chapters = re.split(",|, ", args.chapter)
    print("Handling chapters " + ", ".join(chapters))
    
    for chapter in chapters:
        print("Handling chapter " + chapter)
        handleIndividualChapter(chapter.strip())
else:
    if args.force and os.path.exists("Summary.txt"):
        os.remove("Summary.txt")
        
    for i in tqdm.trange(len(texts)):
        summary = summarize(i)
        
        if args.verbose:
            print('\n------------------------------------------------\nSummary:')
            print(summary)
            print("------------------------------------------------")
            
        with open("Summary.txt", "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open("Summary.txt", "r+", encoding="utf-8") as file:
        fart = file.read()
        fart = fart.strip()
        file.seek(0)
        file.write(fart)
        file.truncate()
        file.close()