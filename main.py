import argparse
import openai
import tqdm
import tiktoken
from distutils.util import strtobool
import time
enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

from dotenv import load_dotenv
load_dotenv()

import re

openai.api_key = "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"
openai.organization = "org-o2qPchMFXjCqioXPTN4pnJot"

parser = argparse.ArgumentParser(description='AI Re:Zero Web Novel Summarizer')
parser.add_argument("-c", "--chapter", type=str, help="Chapter number to summarize. Leave blank to summarize all chapters.", default=None)
args = parser.parse_args()

file = open("Arc 7.txt", "r", encoding="utf-8")

text = file.read()
text = re.sub(r"^.*?(?=Arc 7 Chapter 1 – Initiation).+(?=Arc 7 Chapter 1 – Initiation)", "", text, flags=re.S | re.I) # Remove the table of contents

texts = re.split(r"(?=Arc 7 Chapter \d.*$)|△▼△▼△▼△", text, flags=re.M | re.I) # Split the text into chapters and parts
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
    
# Every chapter has a title in the first line of the text. However, the parts do not have such a title. Iterate through the texts and add a title to the first line of each part, incrementing the chapter number each time until the next time we encounter a chapter title (e.g. "Chapter 2 Part 1").
part = 1
chapter = "0"
for i in range(len(texts)):
    firstline = texts[i].split("\n")[0]
    
    if "Chapter" in firstline and not "Part" in firstline:
        part = 1
        chapter = str(re.search(r"(?<=Chapter )\w+", firstline).group(0))
        
    if not "Chapter" in firstline:
        part += 1
        texts[i] = f"Chapter {chapter} Part {part}\n\n{texts[i]}"

print("Starting summarization in 5 seconds...")
time.sleep(5)

# Print index of the list, with tiktoken encoding
def summarize(i):
    prompt = "\n<END>\n\nCreate a comprehensive plot synopsis of this part of a chapter from a book.\nMake your plot synopsis as lengthy and detailed as possible."
    tokens = len(enc.encode(texts[i])) + len(enc.encode(prompt))
    
    if tokens < 3097:
        model = "gpt-3.5-turbo"
        max_tokens = 1000
    elif tokens < 14385:
        model = "gpt-3.5-turbo-16k"
        max_tokens = 2000
    else:
        print("Too many tokens lol")
    
    print("\n" + texts[i].split("\n")[0]) # Print the chapter title
    print(f"Index: {i} | Tokens: {tokens} | Model: {model}\n") # Print info
    
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
                ],
            )
    except:
        raise Exception("API Error")
    
    summary = APIsummary['choices'][0]['message']['content']
    return summary

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
    
    for i in tqdm.trange(len(indices)):
        i = indices[i]
        summary = summarize(i)
        
        print('------------------------------------------------\nSummary:')
        print(summary)
        print("------------------------------------------------")
        
        # Write to file
        with open(f"Chapter {chapter} Summary.txt", "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open(f"Chapter {chapter} Summary.txt", "r+", encoding="utf-8") as file:
        file.write(file.read().strip())



if args.chapter:
    chapters = re.split(",|, ", args.chapter)
    print("Handling chapters " + ", ".join(chapters))
    
    for chapter in chapters:
        print("Handling chapter " + chapter)
        handleIndividualChapter(chapter.strip())
else:
    for i in tqdm.trange(len(texts)):
        summary = summarize(i)
        
        print('\n------------------------------------------------\nSummary:')
        print(summary)
        print("------------------------------------------------")
        
        with open("Summary.txt", "a", encoding="utf-8") as file:
            firstline = texts[i].split("\n")[0]
            file.write(f"{firstline}\n{summary}\n\n\n")
            
    # Remove whitespace
    with open("Summary.txt", "r+", encoding="utf-8") as file:
        file.write(file.read().strip())