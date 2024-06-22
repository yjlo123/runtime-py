import sys
from tokenizer import Tokenizer, print_tokens
from parser import Parser
from evaluator import Evaluator
from compiler import Compiler

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 vee.py <input_file> [<output-file>]')
        sys.exit(1)

    output_file = None
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]

    with open(sys.argv[1], 'r') as src_file:
        tokenzier = Tokenizer()
        tokens = tokenzier.tokenize(src_file.read())
        # print_tokens(tokens)
    
        parser = Parser(tokens)
        ast = parser.parse()
        ast.pretty_print(indent='', is_last=True)

        evaluator = Evaluator()
        evaluator.evaluate(ast)

        compiler = Compiler()
        compiler.compile(ast)
        for line in compiler.output:
            print(line)