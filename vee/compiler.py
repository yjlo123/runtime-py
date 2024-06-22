from tokenizer import Token, TokenType
from parser import Node, NodeType


class Compiler:
    def __init__(self):
        self.funcs = {}
        self.output = []
        self.var_count = 0
        self.var_pre = ''

    def add(self, line):
        self.output.append(line)

    def get_new_var(self):
        self.var_count += 1
        return f'__v{self.var_count}'

    def gen_let(self, ast):
        name = ast.children[0].token.value
        value = self.compile(ast.children[1])
        self.add(f'let {name} {value}')

    def gen_op(self, op, left, right):
        v = self.get_new_var()
        self.add(f'{op} {v} {left} {right}')
        return Node(NodeType.IDENT, Token(v, TokenType.IDN, 0, 0))

    def gen_func_call(self, func_name, *args):
        self.add(f'{func_name} ' + ' '.join(args[0]))

    def gen_return(self, ast):
        self.add(f'ret {self.compile(ast)}')

    def gen_stmt_list(self, ast):
        for child in ast.children:
            self.compile(child)
        
    def gen_func_def(self, name, args, body):
        self.var_pre = '_'
        self.add(f'def {name}')
        for i, arg in enumerate(args.children):
            # TODO add func scoped var to env
            self.add(f'let _{arg.token.value} ${i}')
        self.compile(body)
        self.add(f'end')
        self.var_pre = ''

    def compile(self, ast):
        node_type = ast.type
        token = ast.token
        children = ast.children
        match node_type:
            case NodeType.VALUE:
                return token.value
            case NodeType.IDENT:
                return f'${self.var_pre}{token.value}'
            case NodeType.FUNC_DEF:
                self.funcs[children[0].token.value] = ast
                self.gen_func_def(children[0].token.value, children[1], children[2])
            case NodeType.RETURN:
                self.gen_return(children[0])
            case NodeType.OPERATOR:
                if token.value == '=':
                    self.gen_let(ast)
                else:
                    left_val = self.compile(children[0])
                    match token.value:
                        case '.':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(f'{left_val}.{right_val}')
                            if children[1].token.value == 'len':
                                return len(left_val)
                    
                    right_val = self.compile(children[1])
                    match token.value:
                        case '+':
                            return self.compile(self.gen_op("add", left_val, right_val))
                        case '-':
                            return int(left_val) - int(right_val)
                        case '*':
                            return self.compile(self.gen_op("mul", left_val, right_val))
                        case '/.':
                            return float(left_val) / float(right_val)
                        case '/':
                            return left_val // right_val
                        case '<':
                            return float(left_val) < float(right_val)
                        case '<=':
                            return float(left_val) <= float(right_val)
                        case '>':
                            return float(left_val) > float(right_val)
                        case '>=':
                            return float(left_val) >= float(right_val)
                        case '==':
                            return left_val == right_val
                        case '..':
                            return range(int(left_val), int(right_val))
                        case '[':
                            return left_val[int(right_val)]
                        case ':':
                            return (left_val, right_val)
                        case _:
                            raise SyntaxError(f'unhandled operator: {token}')
            case NodeType.EXPR_LIST:
                return [self.compile(expr) for expr in children]
            case NodeType.STMT_LIST:
                self.gen_stmt_list(ast)
            case NodeType.FUNC_CALL:
                params = []
                if children:
                    params = self.compile(children[0])
                if token.value == 'print':
                    self.gen_func_call('prt', params)
                elif token.value == 'type':
                    return str(type(params[0]).__name__)
                else:
                    self.gen_func_call('cal ' + token.value, params)
                    # TODO save $ret

                    # func = self.funcs[token.value]
                    # frame = {}
                    # for i, arg in enumerate(func.children[1].children):
                    #     frame[arg.token.value] = params[i]
                    # self.frames.append(frame)
                    # result = self.evaluate(func.children[2])
                    # if type(result) == tuple and len(result) == 2 and result[0] == 'RETURN_SIG':
                    #     return result[1]
                    # return result
            case NodeType.IF:
                cond = self.evaluate(children[0])
                if cond:
                    return self.evaluate(children[1])
                elif len(children) > 2:
                    return self.evaluate(children[2])
            case NodeType.FOR:
                var = children[0].children[0].token.value
                val_range = self.evaluate(children[0].children[1])
                body = children[1]
                this_frame = {}
                self.frames.append(this_frame)
                result = None
                for val in val_range:
                    this_frame[var] = val
                    result = self.evaluate(body)
                    if type(result) == tuple and len(result) == 2 and result[0] == 'RETURN_SIG':
                        break
                return result
        