import os
from tokenizer import Token, TokenType, Tokenizer
from vee_parser import Node, NodeType, Parser


LIB_LIST = 'list.runtime'
LIB_MAP = 'map.runtime'
LIB_TYPE = 'type.runtime'
LIB_PRINT = 'print.runtime'
LIB_LEN = 'len.runtime'

class Compiler:
    def __init__(self, src_file_name):
        self.src_file_name = src_file_name
        self.output = []
        self.var_count = 0
        self.label_count = 0
        self.lambda_count = 0
        self.func_var = None  # set of variables defined in the current function
        self.indent = ''
        self.defined_funcs= set()
        self.lambdas = []
        self.required_libs = set()

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
    
    def get_new_lambda_name(self):
        self.lambda_count += 1
        return f'__lambda{self.lambda_count}'
    
    def create_identity_node(self, name):
        return Node(NodeType.IDENT, Token(name, TokenType.IDN, 0, 0))

    def create_value_node(self, token_type, value):
        return Node(NodeType.VALUE, Token(value, token_type, 0, 0))
    
    def evaluated_identity(self, name):
        # i -> $i
        return self.compile(self.create_identity_node(name))

    def warning(self, msg):
        print(f'[WARNING] {msg}')

    # gen
    def gen_comment(self, msg):
        self.add(f'/ {msg}')
    
    def gen_label(self, name):
        self.add(f'#{name}')

    def gen_let(self, name, value):
        self.add(f'let {name} {value}')

    def gen_op(self, op, left_val, right_val, res_var=None):
        if res_var is None:
            res_var = self.get_new_var()
        self.add(f'{op} {res_var} {left_val} {right_val}')
        return self.create_identity_node(res_var)

    def gen_push_range(self, list_name, start, end):
        var_idx = self.get_new_var()
        self.gen_let(var_idx, start)
        lbl_start = self.get_new_label()
        lbl_end = self.get_new_label()
        self.gen_label(lbl_start)
        self.gen_compare_jump('jeq', self.evaluated_identity(var_idx), end, lbl_end)
        self.add(f'psh ${list_name} {self.evaluated_identity(var_idx)}')
        self.gen_op('add', self.evaluated_identity(var_idx), '1', var_idx)
        self.gen_jump(lbl_start)
        self.gen_label(lbl_end)

    def gen_value_list(self, ast_list):
        var = self.get_new_var()
        self.required_libs.add(LIB_LIST)
        self.add('cal #List')
        self.gen_let(var, '$ret')
        for ast in ast_list:
            self.add(f'cal #List:push {self.evaluated_identity(var)} {str(self.compile(ast))}')
        return self.evaluated_identity(var)
    
    def gen_value_map(self, ast_list):
        var = self.get_new_var()
        self.required_libs.add(LIB_MAP)
        self.add('cal #Map')
        self.gen_let(var, '$ret')
        for ast in ast_list:
            self.add(f'cal #Map:set {self.evaluated_identity(var)} {str(self.compile(ast.children[0]))} {str(self.compile(ast.children[1]))}')
        return self.evaluated_identity(var)

    def gen_list_get(self, arr, idx):
        var = self.get_new_var()
        self.add(f'cal #List:get {arr} {idx}')
        self.gen_let(var, '$ret')
        return self.evaluated_identity(var)

    def gen_list_set(self, container, idx, val):
        self.add(f'cal #List:set {container} {idx} {val}')

    def gen_for2(self, var, range, body_ast):
        # gen using `for`
        self.add(f'for {var} {range}')
        self.increase_indent()
        self.compile(body_ast)
        self.decrease_indent()
        self.add('nxt')

    def gen_for(self, var, range, body_ast):
        # gen without using `for`
        self.required_libs.add(LIB_LIST)

        self.add(f'cal #List:length {range}')
        var_len = self.get_new_var()
        self.gen_let(var_len, '$ret')

        lbl_begin = self.get_new_label()
        lbl_end = self.get_new_label()
        var_idx = self.get_new_var()
        self.gen_let(var_idx, '0')
        self.gen_label(lbl_begin)
        self.gen_compare_jump('jeq', self.evaluated_identity(var_idx), self.evaluated_identity(var_len), lbl_end)

        self.add(f'cal #List:get {range} {self.evaluated_identity(var_idx)}')
        self.gen_let(var, '$ret')

        self.compile(body_ast)
        self.gen_op('add', self.evaluated_identity(var_idx), '1', var_idx)
        self.gen_jump(lbl_begin)
        self.gen_label(lbl_end)

    def gen_while(self, cond_ast, body_ast):
        lbl_begin = self.get_new_label()
        lbl_end = self.get_new_label()
        self.gen_label(lbl_begin)
        cond_res = self.compile(cond_ast)
        self.gen_compare_jump('jne', cond_res, '1', lbl_end)
        self.compile(body_ast)
        self.gen_jump(lbl_begin)
        self.gen_label(lbl_end)

    def gen_get(self, arr, idx, var=None):
        if var is None:
            var = self.get_new_var()
        self.add(f'get {arr} {idx} {var}')
        return self.evaluated_identity(var)
    
    def gen_put(self, arr, idx, val):
        self.add(f'put {arr} {idx} {val}')
    
    def gen_len(self, val):
        self.required_libs.add(LIB_TYPE)
        self.required_libs.add(LIB_LEN)
        var_type = self.get_new_var()
        self.add(f'cal #get_length {val}')
        self.gen_let(var_type, '$ret')
        return self.evaluated_identity(var_type)

    def gen_type(self, val):
        self.required_libs.add(LIB_TYPE)
        var_type = self.get_new_var()
        self.add(f'cal #get_type {val}')
        self.gen_let(var_type, '$ret')
        return self.evaluated_identity(var_type)
    
    def gen_print(self, params):
        self.required_libs.add(LIB_TYPE)
        self.required_libs.add(LIB_PRINT)
        params_var = self.get_new_var()
        self.gen_let(params_var, '[]')
        self.add(f'psh ${params_var} ' + ' '.join(params))
        self.add(f'cal #print ${params_var}')
        self.add('prt \'\'')

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
        if not builtin and func_name[0] != '$' and func_name not in self.defined_funcs:
            # possibly a lambda
            func_name = '$' + func_name
        self.add(f'{"" if builtin else "cal "}{func_name} ' + ' '.join(str(arg) for arg in args[0]) if args else '')

    def gen_return(self, val):
        self.add(f'ret {val}')

    def gen_stmt_list(self, ast):
        last_res = None
        for child in ast.children:
            last_res = self.compile(child)
        return last_res

    def gen_check_arg_default_value(self, index, arg):
        if len(arg.children) > 0:
            default_value_lbl = self.get_new_label()
            arg_done_lbl = self.get_new_label()
            self.gen_compare_jump('jeq', f'${index}', '$nil', default_value_lbl)
            self.gen_jump(arg_done_lbl)
            self.gen_label(default_value_lbl)
            self.gen_let(f'_{arg.token.value}', self.compile(arg.children[0]))
            self.gen_label(arg_done_lbl)

    def gen_func_def(self, name, args, body, closure=None):
        self.func_var = set()
        if closure is not None:
            self.warning(f'Compiling closure is not supported.')
            for arg in closure:
                self.func_var.add(arg)
        for arg in args.children:
            self.func_var.add(arg.token.value)
        self.add(f'def {name}')
        self.increase_indent()
        for i, arg in enumerate(args.children):
            self.gen_let(f'_{arg.token.value}', f'${i}')
            self.gen_check_arg_default_value(i, arg)
        last_res = self.compile(body)
        if last_res is not None:
            self.gen_return(last_res)
        self.decrease_indent()
        self.add(f'end')
        self.func_var = None

    def compile(self, ast):
        node_type = ast.type
        token = ast.token
        children = ast.children
        match node_type:
            case NodeType.VALUE:
                # value boolean, e.g. condtion in if-else
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
                # identity boolean, e.g. user literal
                if token.type == TokenType.IDN and token.value == 'true':
                    return 1
                elif token.type == TokenType.IDN and token.value == 'false':
                    return 0
                elif token.type == TokenType.IDN and token.value in self.defined_funcs:
                    return token.value
                elif self.func_var and token.value in self.func_var:
                    return f'$_{token.value}'
                elif token.value == 'this':
                    return '$_data'
                return f'${token.value}'
            case NodeType.FUNC_DEF:
                func_name = children[0].token.value
                func_args = children[1]
                func_body = children[2]
                self.defined_funcs.add(func_name)
                self.gen_func_def(func_name, func_args, func_body)
            case NodeType.RETURN:
                self.gen_return(self.compile(children[0]))
            case NodeType.OPERATOR:
                left = children[0] if len(children) >= 1 else None
                right = children[1] if len(children) >= 2 else None
                right_val = None
                if token.value == '=':
                    right_val = self.compile(right)
                    if left.token.type == TokenType.SYM and left.token.value == '.':
                        dot_left_val = self.compile(left.children[0])
                        dot_right_val = left.children[1].token.value
                        self.gen_put(dot_left_val, dot_right_val, right_val)
                    elif left.token.type == TokenType.SYM and left.token.value == '[':
                        dot_left_val = self.compile(left.children[0])
                        dot_right_val = self.compile(left.children[1])
                        self.gen_list_set(dot_left_val, dot_right_val, right_val)
                    else:
                        prefix = ''
                        if self.func_var is not None:
                            # in function scope, define all new var as local
                            if left.token.value not in self.func_var:
                                self.func_var.add(left.token.value)
                            prefix = '_'
                        self.gen_let(prefix + left.token.value, right_val)
                else:
                    match token.value:
                        case '=>':
                            lambda_name = self.get_new_lambda_name()
                            # add lambda to queue, and will be compiled at global
                            self.lambdas.append((lambda_name, left, right, self.func_var))
                            return lambda_name
                    left_val = self.compile(left)
                    match token.value:
                        case '.':
                            if left.token.type==TokenType.NUM and right.token.type==TokenType.NUM:
                                right_val = self.compile(right)
                                return float(f'{left_val}.{right_val}')
                            elif children[1].token.value == 'len':
                                # bult-in len
                                return self.gen_len(left_val)
                            else:
                                instance_ref = left_val
                                if right.type == NodeType.IDENT:
                                    # instance property
                                    return self.gen_get(instance_ref, right.token.value)
                                    # TODO get static property
                                elif right.type == NodeType.FUNC_CALL:
                                    # instance method call
                                    #  find class name for the instance
                                    class_name_var = self.get_new_var()
                                    if instance_ref[0] != '$':
                                        # calling class static method
                                        self.gen_let(class_name_var, instance_ref)
                                    else:
                                        self.gen_get(instance_ref, '__class', class_name_var)
                                    self.gen_op('add', self.evaluated_identity(class_name_var), ':', res_var=class_name_var)
                                    self.gen_op('add', self.evaluated_identity(class_name_var), right.token.value, res_var=class_name_var)
                                    method_full_name = f'{self.evaluated_identity(class_name_var)}'
                                    params = self.compile(right.children[0])
                                    params = [instance_ref] + params
                                    self.gen_func_call(method_full_name, params)
                                    new_var = self.get_new_var()
                                    self.gen_let(new_var, '$ret')
                                    return self.evaluated_identity(new_var)
                        case '&&':
                            res = self.get_new_var()
                            lbl_result_false = self.get_new_label()
                            lbl_check_done = self.get_new_label()
                            self.add(f'jeq {left_val} 0 {lbl_result_false}')
                            right_val = self.compile(right)
                            self.add(f'jeq {right_val} 0 {lbl_result_false}')
                            self.gen_let(res, '1')
                            self.gen_jump(lbl_check_done)
                            self.gen_label(lbl_result_false)
                            self.gen_let(res, '0')
                            self.gen_label(lbl_check_done)
                            return self.compile(self.create_identity_node(res))
                        case '||':
                            res = self.get_new_var()
                            lbl_result_true = self.get_new_label()
                            lbl_check_done = self.get_new_label()
                            self.add(f'jeq {left_val} 1 {lbl_result_true}')
                            right_val = self.compile(right)
                            self.add(f'jeq {right_val} 1 {lbl_result_true}')
                            self.gen_let(res, '0')
                            self.gen_jump(lbl_check_done)
                            self.gen_label(lbl_result_true)
                            self.gen_let(res, '1')
                            self.gen_label(lbl_check_done)
                            return self.compile(self.create_identity_node(res))

                    if right is not None and right_val is None:
                        right_val = self.compile(right)
                    match token.value:
                        case '+':
                            return self.compile(self.gen_op('add', left_val, right_val))
                        case '-':
                            if right is None:
                                return self.compile(self.gen_op('sub', 0, left_val))
                            return self.compile(self.gen_op('sub', left_val, right_val))
                        case '*':
                            return self.compile(self.gen_op('mul', left_val, right_val))
                        case '/.':
                            return self.compile(self.gen_op('div', left_val, right_val))
                        case '/':
                            return self.compile(self.gen_op('div', left_val, right_val))
                        case '%':
                            return self.compile(self.gen_op('mod', left_val, right_val))
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
                        case '!=':
                            return self.compile(self.gen_compare('jne', left_val, right_val))
                        case '..':
                            range_var = self.get_new_var()
                            self.gen_let(range_var, '[]')
                            self.gen_push_range(range_var, left_val, right_val)
                            # conver raw list to List instance
                            self.required_libs.add(LIB_LIST)
                            self.add(f'cal #buildList {self.evaluated_identity(range_var)}')
                            range_list_var = self.get_new_var()
                            self.gen_let(range_list_var, '$ret')
                            return self.evaluated_identity(range_list_var)
                        case '[':
                            return self.gen_list_get(left_val, right_val)
                        case ':':
                            return (left_val, right_val)
                        case _:
                            raise SyntaxError(f'unhandled operator: {token}')
            case NodeType.EXPR_LIST:
                if token.value == '[':
                    return self.gen_value_list(children)
                elif token.value == '{':
                    return self.gen_value_map(children)
                else:
                    return [self.compile(expr) for expr in children]
            case NodeType.STMT_LIST:
                return self.gen_stmt_list(ast)
            case NodeType.FUNC_CALL:
                params = []
                if children:
                    params = self.compile(children[0])
                if token.value == 'print':
                    return self.gen_print(params or ['\'\''])
                elif token.value == 'type':
                    return self.gen_type(params[0])
                else:
                    self.gen_func_call(token.value, params)
                    new_var = self.get_new_var()
                    self.gen_let(new_var, '$ret')
                    return self.evaluated_identity(new_var)
            case NodeType.IF:
                lbl_end_if = self.get_new_label()
                res_var = self.get_new_var()
                # the result of the if-else-expression for returning
                self.gen_let(res_var, '$nil')
                for cond_index in range(len(children) // 2):
                    cond = children[cond_index * 2]
                    lbl_true = self.get_new_label()
                    lbl_end_true = self.get_new_label()
                    self.gen_compare_jump('jeq', self.compile(cond), '1', lbl_true)
                    # condition false, and jump to end of true
                    self.gen_jump(lbl_end_true)
                    # true block, and jump to the very end
                    self.gen_label(lbl_true)
                    self.gen_let(res_var, self.compile(children[cond_index * 2 + 1]))
                    self.gen_jump(lbl_end_if)
                    self.gen_label(lbl_end_true)
                self.gen_label(lbl_end_if)
                return self.evaluated_identity(res_var)
            case NodeType.FOR:
                var = children[0].token.value
                val_range = self.compile(children[1])
                body = children[2]
                self.gen_for(var, val_range, body)
            case NodeType.WHILE:
                self.gen_while(children[0], children[1])
            case NodeType.CLASS:
                class_name = children[0].token.value
                self.defined_funcs.add(class_name)
                # gen contructor
                self.add(f'def {class_name}')
                self.increase_indent()
                var_data = '_data'
                self.gen_let(var_data, '{}')
                self.gen_put(self.evaluated_identity(var_data), '__class', class_name)
                lbl_end_of_init = self.get_new_label()
                for stmt in children[1].children:
                    if stmt.type == NodeType.OPERATOR and stmt.token.value == '=':
                        # gen attribute
                        left = stmt.children[0].token.value
                        right = self.compile(stmt.children[1])
                        self.add(f'put {self.evaluated_identity(var_data)} {left} {right}')
                    if stmt.type == NodeType.FUNC_DEF and stmt.children[0].token.value == 'init':
                        self.gen_compare_jump('jne', '$#', len(stmt.children[1].children), lbl_end_of_init)
                        # gen init
                        self.func_var = set()
                        for i, arg in enumerate(stmt.children[1].children):
                            self.add(f'let _{arg.token.value} ${i}')
                            self.func_var.add(arg.token.value)
                        self.compile(stmt.children[2])
                self.gen_label(lbl_end_of_init)
                self.gen_return(self.evaluated_identity(var_data))
                self.decrease_indent()
                self.add(f'end')
                self.func_var = None
                # gen methods
                for stmt in children[1].children:
                    if stmt.type == NodeType.FUNC_DEF and stmt.children[0].token.value != 'init':
                        method_name = stmt.children[0].token.value
                        method_args = stmt.children[1].children
                        method_body = stmt.children[2]
                        self.add(f'def {class_name}:{method_name}')
                        self.increase_indent()

                        self.add(f'let _data $0')
                        self.func_var = set()
                        for i, arg in enumerate(method_args):
                            self.add(f'let _{arg.token.value} ${i+1}')
                            self.func_var.add(arg.token.value)
                            self.gen_check_arg_default_value(i+1, arg)
    
                        last_res = self.compile(method_body)
                        if last_res is not None:
                            self.gen_return(last_res)
                        self.decrease_indent()
                        self.add(f'end')
                        self.func_var = None
            case NodeType.IMPORT:
                path = os.path.dirname(self.src_file_name)
                # TODO import from multi level path
                #      resolve dependencies
                file_name = children[0].children[0].token.value + '.vee'
                value_name = children[0].children[1].token.value
                file_path = os.path.join(path, file_name)
                with open(file_path, 'r') as src_file:
                    tokenizer = Tokenizer()
                    tokens = tokenizer.tokenize(src_file.read())
                    parser = Parser(tokens)
                    imported_ast = parser.parse()
                    for stmt in imported_ast.children:
                        # TODO support importing var values
                        if stmt.type in (NodeType.FUNC_DEF, NodeType.CLASS) and stmt.children[0].token.value == value_name:
                            self.compile(stmt)
                            break
        
    def compile_ast(self, ast):
        self.required_libs = set()
        self.gen_comment('==== runtime script ====')
        self.compile(ast)
        for (name, args, body, closure) in self.lambdas:
            # compile lambda in global
            self.gen_func_def(name, args, body, closure=closure)
        # except Exception as e:
        #     print('********** ERROR **********')
        #     print(e)
        #     print('***************************')

    def get_linked_out(self):
        lib_out = []
        for lib in self.required_libs:
            with open('compiler_lib/' + lib, 'r') as lib_src:
                while line := lib_src.readline():
                    lib_out.append(line.rstrip())
        return lib_out + self.output
