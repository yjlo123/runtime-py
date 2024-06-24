from tokenizer import Token, TokenType
from parser import Node, NodeType


class Compiler:
    def __init__(self):
        self.funcs = {}
        self.output = []
        self.var_count = 0
        self.label_count = 0
        self.func_var = set()
        self.indent = ''

    # utils
    def increase_indent(self):
        self.indent += ' '
    
    def decrease_indent(self):
        self.indent = self.indent[:-1]

    def add(self, line):
        self.output.append(self.indent + line)

    def get_new_var(self):
        self.var_count += 1
        return f'__var{self.var_count}'
    
    def get_new_label(self):
        self.label_count += 1
        return f'__lbl{self.label_count}'
    
    def create_identity_node(self, name):
        return Node(NodeType.IDENT, Token(name, TokenType.IDN, 0, 0))

    def create_value_node(self, token_type, value):
        return Node(NodeType.VALUE, Token(value, token_type, 0, 0))
    
    # gen
    def gen_comment(self, msg):
        self.add(f'/ {msg}')
    
    def gen_label(self, name):
        self.add(f'#{name}')

    def gen_let(self, name, value):
        self.add(f'let {name} {value}')

    def gen_op(self, op, left_val, right_val, res_var=None):
        if not res_var:
            res_var = self.get_new_var()
        self.add(f'{op} {res_var} {left_val} {right_val}')
        return self.create_identity_node(res_var)

    def gen_push_range(self, list_name, start, end):
        var_idx = self.get_new_var()
        self.gen_let(var_idx, start)
        lbl_start = self.get_new_label()
        lbl_end = self.get_new_label()
        self.gen_label(lbl_start)
        self.gen_compare_jump('jeq', self.compile(self.create_identity_node(var_idx)), end, lbl_end)
        self.add(f'psh ${list_name} {self.compile(self.create_identity_node(var_idx))}')
        self.gen_op('add', self.compile(self.create_identity_node(var_idx)), '1', var_idx)
        self.gen_jump(lbl_start)
        self.gen_label(lbl_end)

    def gen_value_list(self, ast_list):
        var = self.get_new_var()
        self.gen_let(var, '[]')
        self.add(f'psh ${var} ' + ' '.join([str(self.compile(ast)) for ast in ast_list]))
        return self.compile(self.create_identity_node(var))

    def gen_for(self, var, range, body_ast):
        self.add(f'for {var} {range}')
        self.increase_indent()
        self.compile(body_ast)
        self.decrease_indent()
        self.add('nxt')


    def gen_compare(self, op, left_val, right_val):
        res = self.get_new_var()
        lbl_true = self.get_new_label()
        lbl_end_true = self.get_new_label()
        self.add(f'{op} {left_val} {right_val} {lbl_true}')
        self.gen_let(res, '0')
        self.gen_jump(lbl_end_true)
        self.gen_label(lbl_true)
        self.gen_let(res, '1')
        self.gen_label(lbl_end_true)
        return self.create_identity_node(res)

    def gen_compare_jump(self, op, left_val, right_val, label_t):
        self.add(f'{op} {left_val} {right_val} {label_t}')
    
    def gen_jump(self, label):
        self.add(f'jmp {label}')

    def gen_func_call(self, func_name, *args, builtin=False):
        self.add(f'{"" if builtin else "cal "}{func_name} ' + ' '.join(str(arg) for arg in args[0]) if args else '')

    def gen_return(self, expr_ast):
        self.add(f'ret {self.compile(expr_ast)}')

    def gen_stmt_list(self, ast):
        for child in ast.children:
            self.compile(child)
        
    def gen_func_def(self, name, args, body):
        for arg in args.children:
            self.func_var.add(arg.token.value)
        self.add(f'def {name}')
        self.increase_indent()
        for i, arg in enumerate(args.children):
            self.add(f'let _{arg.token.value} ${i}')
        self.compile(body)
        self.decrease_indent()
        self.add(f'end')
        self.func_var = set()

    def compile(self, ast):
        node_type = ast.type
        token = ast.token
        children = ast.children
        match node_type:
            case NodeType.VALUE:
                if token.type == TokenType.IDN and token.value == 'true':
                    return 1
                elif token.type == TokenType.IDN and token.value == 'false':
                    return 0
                
                if token.type == TokenType.STR:
                    return f"'{token.value}'"
                elif token.type == TokenType.NUM:
                    if type(token.value) == int:
                        return token.value 
                    if '.' in token.value:
                        return float(token.value)
                    else:
                        return int(token.value)
                return token.value
            case NodeType.IDENT:
                if token.value in self.func_var:
                    return f'$_{token.value}'
                return f'${token.value}'
            case NodeType.FUNC_DEF:
                self.funcs[children[0].token.value] = ast
                self.gen_func_def(children[0].token.value, children[1], children[2])
            case NodeType.RETURN:
                self.gen_return(children[0])
            case NodeType.OPERATOR:
                if token.value == '=':
                    self.gen_let(ast.children[0].token.value, self.compile(ast.children[1]))
                else:
                    left_val = self.compile(children[0])
                    right_val = self.compile(children[1])
                    match token.value:
                        case '.':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(f'{left_val}.{right_val}')
                            if children[1].token.value == 'len':
                                # TODO bult-in len
                                return len(left_val)
                    match token.value:
                        case '+':
                            return self.compile(self.gen_op("add", left_val, right_val))
                        case '-':
                            return self.compile(self.gen_op("sub", left_val, right_val))
                        case '*':
                            return self.compile(self.gen_op("mul", left_val, right_val))
                        case '/.':
                            return self.compile(self.gen_op("div", left_val, right_val))
                        case '/':
                            return left_val // right_val
                        case '<':
                            return self.compile(self.gen_compare('jlt', left_val, right_val))
                        case '<=':
                            res_lt = self.compile(self.gen_compare('jlt', left_val, right_val))
                            res_eq = self.compile(self.gen_compare('jeq', left_val, right_val))
                            sum_res = self.compile(self.gen_op("add", res_lt, res_eq))
                            return self.compile(self.gen_compare('jgt', sum_res, 0))
                        case '>':
                            return self.compile(self.gen_compare('jgt', left_val, right_val))
                        case '>=':
                            res_lt = self.compile(self.gen_compare('jgt', left_val, right_val))
                            res_eq = self.compile(self.gen_compare('jeq', left_val, right_val))
                            sum_res = self.compile(self.gen_op("add", res_lt, res_eq))
                            return self.compile(self.gen_compare('jgt', sum_res, 0))
                        case '==':
                            return self.compile(self.gen_compare('jeq', left_val, right_val))
                        case '&&':
                            sum_res = self.compile(self.gen_op("add", left_val, right_val))
                            return self.compile(self.gen_compare('jgt', sum_res, 1))
                        case '||':
                            sum_res = self.compile(self.gen_op("add", left_val, right_val))
                            return self.compile(self.gen_compare('jgt', sum_res, 0))
                        case '..':
                            range_var = self.get_new_var()
                            self.gen_let(range_var, '[]')
                            self.gen_push_range(range_var, left_val, right_val)
                            return self.compile(self.create_identity_node(range_var))
                        case '[':
                            return left_val[int(right_val)]
                        case ':':
                            return (left_val, right_val)
                        case _:
                            raise SyntaxError(f'unhandled operator: {token}')
            case NodeType.EXPR_LIST:
                if token.value == '[':
                    return self.gen_value_list(children)
                else:
                    return [self.compile(expr) for expr in children]
            case NodeType.STMT_LIST:
                self.gen_stmt_list(ast)
            case NodeType.FUNC_CALL:
                params = []
                if children:
                    params = self.compile(children[0])
                if token.value == 'print':
                    self.gen_func_call('prt', params, builtin=True)
                elif token.value == 'type':
                    return str(type(params[0]).__name__)
                else:
                    self.gen_func_call(token.value, params)
                    new_var = self.get_new_var()
                    self.gen_let(new_var, '$ret')
                    return self.compile(self.create_identity_node(new_var))
            case NodeType.IF:
                lbl_end_if = self.get_new_label()
                for cond_index in range(len(children) // 2):
                    cond = children[cond_index * 2]
                    lbl_true = self.get_new_label()
                    lbl_end_true = self.get_new_label()
                    self.gen_compare_jump('jeq', self.compile(cond), '1', lbl_true)
                    # condition false, and jump to end of true
                    self.gen_jump(lbl_end_true)
                    # true block, and jump to the very end
                    self.gen_label(lbl_true)
                    self.compile(children[cond_index * 2 + 1])
                    self.gen_jump(lbl_end_if)
                    self.gen_label(lbl_end_true)
                self.gen_label(lbl_end_if)
            case NodeType.FOR:
                var = children[0].children[0].token.value
                val_range = self.compile(children[0].children[1])
                body = children[1]
                self.gen_for(var, val_range, body)
        
    def compile_ast(self, ast):
        self.gen_comment('==== runtime script ====')
        self.compile(ast)
        # except Exception as e:
        #     print('********** ERROR **********')
        #     print(e)
        #     print('***************************')
