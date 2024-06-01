from enum import Enum
from tokenizer import TokenType

class Node:
    def __init__(self, type, token):
        self.type = type
        self.token = token
        self.children = []

class NodeType(Enum):
    ROOT = 1
    OPERATOR = 2
    FUNCTION = 3
    FOR = 4
    IF = 5
    TODO = 999

KEY_WORDS = [
    'class',
    'func',
    'for',
    'if',
    'else'
]

class Parser:
    def parse(tokens):
        ptr = 0
        root = Node(NodeType.ROOT, None)
        ast = root
        while ptr < len(tokens):
            t = tokens[ptr]
            if t in KEY_WORDS:
                pass
            else:
                # expression
                stack = []
                if t.type != TokenType.SYM:
                    stack.append(Node(NodeType.TODO, t))
                else:
                    # TODO
                    pass
        return root