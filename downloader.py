# Downloads the arcs
import gdown
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import os
import argparse


parser = argparse.ArgumentParser(prog="sumzero-dl", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("arcs", type=str, help="The arcs to download and process. Comma separated. Put \"all\" to process all available arcs.", default=None)
parser.add_argument("-d", "--dir", metavar="DIR", type=str, help="Working directory (input & output) path", default="")
parser.add_argument("-c", help="Delete the epubs after converting to txt", action="store_true")
parser.add_argument("--dry-run", help="Don't write to the files", action="store_true")
args = parser.parse_args()

arcs = {
    "Arc 4": "https://drive.google.com/uc?id=1DdYKspFb5g8tGu7vEMjYRQTEu5OiWXwq",
    "Arc 5": "https://drive.google.com/uc?id=1dscUL367uWH9ZiN9YZoPJlCPE-g7sHkp",
    "Arc 6": "https://drive.google.com/uc?id=1DicrC_gQKdJFQWt95Lfn5hizbPO9CtPZ",
    "Arc 7": "https://drive.google.com/uc?id=14pCMhpQ2LBEc3TGfvwqiAtxHZ6LgUVee"
}

directory = os.path.abspath(args.dir) if args.dir else os.path.join(os.getcwd())

if not os.path.exists(directory):
    os.makedirs(directory)

def handle_arc(arc: int):
    gdown.cached_download(arcs[f"Arc {arc}"], os.path.join(directory, f"Arc {arc}.epub"))

    def convertToText(epubfile):
        book = epub.read_epub(epubfile)
        texts = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            texts.append(item.get_content().decode("utf-8"))
        return texts

    html = convertToText(os.path.join(directory, f"Arc {arc}.epub"))

    for i in range(len(html)):
        html[i] = BeautifulSoup(html[i], "html.parser").text.strip()

    with open(os.path.join(directory, f"Arc {arc}.txt"), "w", encoding="utf-8") as file:
        file.write("\n\n".join(html))
        
    if args.c:
        print(f"Deleting Arc {arc}.epub")
        os.remove(os.path.join(directory, f"Arc {arc}.epub"))

if args.arcs == "all":
    for arc in arcs:
        handle_arc(arc)
elif args.arcs:
    for arc in args.arcs.split(","):
        handle_arc(arc)