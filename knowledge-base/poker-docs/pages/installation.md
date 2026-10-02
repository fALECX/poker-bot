# installation

Source: https://docs.poker.monashcoding.com/installation/

Installation | macpoker docs- - - - - Skip to content
Requirements
Section titled “Requirements”
Python 3.10 or newer. The SDK has no dependencies.
Install the SDK
Section titled “Install the SDK”
- Terminal windowpip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
A virtual environment is a good idea:
Terminal windowpython -m venv .venv
source .venv/bin/activate # windows: .venv\Scripts\activate
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
Check it works:
Terminal windowmacpoker play house:call house:random --deals 10
The scaffold
Section titled “The scaffold”
The quickest start is the
scaffold zip:
a folder with a working main.py and a README. Edit, test, zip, upload.
What runs in the tournament
Section titled “What runs in the tournament”
Your bot runs inside a sandbox with:
- Python 3.12
- the macpoker SDK
- numpy
- the Python standard library
- no network access, no other packages, no GPU
If your bot imports anything outside that list, it will fail validation.
Limit
Value
CPU
1 core
Memory
512 MB
Filesystem
read-only, plus a 64 MB /tmp wiped after each game
Submission
zip up to 20 MB unpacked, at most 300 files
Clock
30 s time bank per game, plus 0.1 s per hand
