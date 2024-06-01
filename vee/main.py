import sys
from tokenizer import Tokenizer, print_tokens

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 vee.py <input_file> [<output-file>]')
        sys.exit(1)
    
    output_file = None
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]

    tokenzier = Tokenizer()

    with open(sys.argv[1], 'r') as src_file:
        tokens = tokenzier.tokenize(src_file.read())
        print_tokens(tokens)
