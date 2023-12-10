# rezero-summarizer
AI Summarizer for the Re:Zero Web Novel

# Inspiration
This project was created while I was reading Arc 7 of the Re:Zero Web Novel. Arc 7 is a very long chapter, and introduces many new characters. I found it particularly hard to follow the events and understand what was going on. I found the summaries on the Re:Zero Wiki helpful, but they were incomplete and stopped after the first couple of chapters of Arc 7. Because of this, I decided to create my own summarizer to help me understand the events of Arc 7 better. Instead of needing to go back a chapter and reread, I could just quickly read the summary and continue on with the story, having a better understanding of what was going on due to the easy to digest nature of a summary. I hope that this project can help others who are reading the Re:Zero Web Novel as well, and can help them understand the story better.

# Disclaimer
Please do not use this as a substitute for reading the Re:Zero Web Novel. This is meant to be a supplement to the story, a way to understand it better (to help with reading comprehension), not a replacement for it. I highly recommend reading the Re:Zero Web Novel, as it is a great story and will be more enjoyable than reading an AI generated summary.
# Installation

### Windows
This project uses pyinstaller to create self contained binaries. Both the main script and the downloader script are included. These binaries don't require python or any dependencies to be installed. You can grab them from the [releases page](https://github.com/smallketchup82/rezero-summarizer/releases/latest). Unzip the zip file and refer to the usage section for help.

To input your OpenAI API credentials, use the `--api-key` and `--org` options or pass them as environment variables in your shell. Refer to .env.example for the names of the variables.

### Other (Python)
I'd recommend using Python 3.10
1. Clone the repository
2. Install the requirements
```bash
pip install -r requirements.txt
```
3. Run the downloader to download and process the arcs. Refer to the usage section for help
4. Rename .env.example to .env and input your OpenAI API credentials or use the CLI arguments

# Usage (windows binaries)
The help documentation (`--help`) for both scripts adequately explain most of the options. I'd recommend reading them before using the scripts.  
These usages docs are for the windows binaries, however they are basically the same thing for python. Just subsitute the command with `python downloader.py [args]` or `python main.py [args]`
Make sure you're running the commands in the same folder as the binaries
### Downloader
The summarizer only works on full arc downloads. At the moment, these are only arcs 4, 5, 6, and 7. The downloader script will download the arcs and process them and output them to their respective text files.

Usage
```bash
.\sumzero-dl.exe --help
```
The script will, by default, download all of the arcs. While I would recommend this, you can download specific arcs if you'd like.

To download specific arcs, pass them as comma separated values (with no spaces).
### Summarizer
The summarizer script will generate a summary for the given arc/chapter. The script will, by default, generate a summary for all of the chapters in the arc. I don't really recommend this since its both time consuming, but also expensive. Only do it if you are willing to spend the money.

Usage
```bash
.\sumzero.exe --help
```

The defaults are the optimal settings for the summarizer. I don't recommend really recommend changing them, but you can if you want to.

You must pass the `-i` argument with the path to the Arc text file, generated via the downloader. The summarizer will refuse to do anything unless you supply the Arc text file.

Running the command will display a list of chapters in the arc. You can select which chapters you want to summarize by passing them as comma separated values (with no spaces).

To summarize the entire arc, press "`a`" in the chapter selection menu and press enter. To merge the summaries into a single summary for the arc, pass the `--merge` (`-m`) flag.

# How it works
It's mostly just a ton of regex and string manipulation. Every chapter in the full arc downloads are split into parts. The summarizer will go through every chapter in the arc and identify the parts in the chapter. It then figures out how long each part is, and decides whether to use gpt-3.5-turbo or gpt-3.5-turbo-16k. It then generates a summary for each part, and combines them into a single summary for the chapter. If instructed to summarize the entire arc, it combines all of the chapter summaries into a single summary for the arc.

# Building

### Requirements
- Python 3.10

1. Clone the repository
2. Install the requirements
```bash
pip install -r requirements.txt
```
3. Install pyinstaller
```bash
pip install pyinstaller
```
4. Build the binaries
```bash
pyinstaller main.spec
```
