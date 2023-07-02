import datetime
import json
import random
import sys
import time

class Parser:
    def parse(self, src):
        program = []
        labels = {
            'global': {},
            'function': {}
        }
        funcs = {}

        lines = src.split('\n')
        _current_func = None
        for ln, l in enumerate(lines):
            l = l.strip()
            if l == '' or l.startswith('/'):
                program.append([])
                continue
            
            # label
            if l[0] == '#':
                label_name = l[1:].strip()
                if _current_func is not None:
                    labels[_current_func][label_name] = ln
                else:
                    labels['global'][label_name] = ln
            if l.startswith('def '):
                func_name = l[3:].strip().split(' ')[0]
                funcs[func_name] = ln
                labels[func_name] = {}
                _current_func = func_name
            if l.strip() == 'end':
                # no nested funcs
                _current_func = None
            line_tokens = self._tokenize(l)
            program.append(line_tokens)
        return (program, labels, funcs)

    def _tokenize(self, line):
        tokens = []
        current = ''
        i = 0
        while i < len(line):
            c = line[i]
            if c == '\'':
                # string
                if current != '':
                    tokens.append(current)
                    current = ''
                current += line[i]
                i += 1
                while i < len(line):
                    if line[i] == '\'':
                        break
                    cc = line[i]
                    if cc == '\\':
                        i += 1
                        if i > len(line):
                            print("Unterminated string")
                        cc = line[i]
                        esc_map = {
                            'b': '\b',
                            'n': '\n',
                            't': '\t',
                            "'": "'",
                        }
                        cc = esc_map.get(cc, '\\'+cc)
                    current += cc
                    i += 1
                current += line[i]
            elif c == '/':
                # comment
                break
            elif c == ' ':
                # add token
                if len(current) > 0:
                    tokens.append(current)
                    current = ''
            else:
                current += c
            i += 1
        if len(current) > 0:
            tokens.append(current)
        return tokens

class FileLogger:
    def print(self, text, end=None):
        text += '\n' if end is None else end
        with open("log.txt", 'a') as log_file:
            log_file.write(text)

class Evaluator:
    def __init__(self, output_device=None):
        self.extended = {}
        self.display = None  # default standard out
        if output_device == 'oled':
            from oled import oled
            self.display = oled.Display
        elif output_device == 'file':
            self.display = FileLogger()

    def extend(self, cmd, handler):
        self.extended[cmd] = handler

    def _assign(self, env, var, val):
        if (var == 'ret' or var[0] == '_') and env['stack']:
            env['stack'][-1]['env'][var] = val
        else:
            env['global'][var] = val

    def _get_var_val(self, env, var):
        if (var == 'ret' or var[0] == '_') and env['stack']:
            return env['stack'][-1]['env'][var]
        else:
            return env['global'].get(var)

    def _goto_label(self, env, lbl, name):
        lbl_set = None
        if env['stack']:
            func_stack_obj = env['stack'][-1]
            lbl_set = lbl[func_stack_obj['func']]
        else:
            lbl_set = lbl['global']
        if name in lbl_set:
            env['pc'] = lbl_set[name] - 1
        else:
            print('ERR invalid label in scope', env['pc']+1, name)

    def _compare(self, v1, v2):
        if type(v1) == list and type(v2) == list:
            if len(v1) != len(v2):
                return False
            for i in range(len(v1)):
                if not self._compare(v1[i], v2[i]):
                    return False
            return True
        return v1 == v2

    def _is_numeric(self, string):
        try:
            int(string)
            return True
        except:
            return  False

    def _print(self, env, ts):
        res = self.expr(env, ts[1])
        end_char = self.expr(env, ts[2]) if len(ts) > 2 else '\n'
        if res is None:
            res = '(nil)'
        if self.display:
            self.display.print(str(res), end_char)
        else:
            print(str(res), end=end_char)

    def _input(self, env, var):
        text = input()
        self._assign(env, var, text)

    def _goto_if_false(self, prog, env):
        env['pc'] += 1
        if_stack = 0
        while env['pc'] <= len(prog):
            cur = prog[env['pc']]
            if cur:
                cur = cur[0]
                if cur in ('ife', 'ifg'):
                    if_stack += 1
                elif cur == 'fin':
                    if if_stack == 0:
                        return
                    else:
                        if_stack -= 1
                elif cur == 'els':
                    if if_stack == 0:
                        return
            env['pc'] += 1

    def _goto_if_end(self, prog, env):
        if_stack = 0
        while env['pc'] <= len(prog):
            cur = prog[env['pc']]
            if cur:
                cur = cur[0]
                if cur in ('ife', 'ifg'):
                    if_stack += 1
                elif cur == 'fin':
                    if if_stack == 0:
                        return
                    else:
                        if_stack -= 1
            env['pc'] += 1

    def _goto_end(self, prog, env, keyword):
        while env['pc'] < len(prog) and (not prog[env['pc']] or prog[env['pc']][0] != keyword):
            env['pc'] += 1

    def _back_to_loop_head(self, prog, env):
        for_stack = 0
        env['pc'] -= 1
        while env['pc'] > 0:
            cur = prog[env['pc']]
            if cur:
                cur = cur[0]
                if cur == 'for':
                    if for_stack == 0:
                        env['pc'] -= 1
                        return
                    for_stack -= 1
                elif cur == 'nxt':
                    for_stack += 1
            env['pc'] -= 1

    def _goto_loop_end(self, prog, env):
        env['pc'] += 1
        for_stack = 0
        while env['pc'] < len(prog):
            cur = prog[env['pc']]
            if cur:
                cur = cur[0]
                if cur == 'for':
                    for_stack += 1
                elif cur == 'nxt':
                    if for_stack == 0:
                        return
                    for_stack -= 1
            env['pc'] += 1

    def expr(self, env, exp):
        res = None
        if exp[0] == '$':
            var_name = exp[1:]
            if var_name == 'nil':
                res = None
            else:
                # env val
                val = None
                func_stack_obj = env['stack'][-1] if env['stack'] else None
                if func_stack_obj and var_name in func_stack_obj['env']:
                    # function scoped var
                    if self._is_numeric(var_name):
                        # function arg
                        val = func_stack_obj['env'][var_name]
                    else:
                        val = func_stack_obj['env'][var_name]
                else:
                    # global var
                    val = env['global'].get(var_name)
                
                if val is None:
                    res = None
                elif type(val) == str and len(val) > 2 and val[0] == '\'' and val[-1] == '\'':
                    res = val[1:-1]
                else:
                    res = val
        elif exp == '[]':
            res = []
        elif exp == '{}':
            res = {}
        elif exp[0] == '\'' and exp[-1] == '\'':
            res = exp[1:-1]
        elif self._is_numeric(exp):
            res = int(exp)
        else:
            res = exp

        if type(res) == bool:
            res = int(res)
        return res



    def eval(self, ts, env, lbl, fun, program):
        self.env = env
        if len(ts) == 0:
            return
        if ts[0][0] == '#':
            return
        cmd = ts[0]
        if cmd == 'let':
            var = ts[1]
            val = self.expr(env, ts[2])
            self._assign(env, var, val)
        elif cmd == 'prt':
            self._print(env, ts)
        elif cmd == 'inp':
            self._input(env, ts[1])
        elif cmd == 'prs':
            data = self.expr(env, ts[2])
            self._assign(env, ts[1], json.loads(data))


        # === JUMP ===
        elif cmd == 'jmp':
            self._goto_label(env, lbl, ts[1])
        elif cmd == 'jeq':
            if self._compare(self.expr(env, ts[1]), self.expr(env, ts[2])):
                self._goto_label(env, lbl, ts[3])
        elif cmd == 'jne':
            if not self._compare(self.expr(env, ts[1]), self.expr(env, ts[2])):
                self._goto_label(env, lbl, ts[3])
        elif cmd == 'jlt':
            if self.expr(env, ts[1]) < self.expr(env, ts[2]):
                self._goto_label(env, lbl, ts[3])
        elif cmd == 'jgt':
            if int(self.expr(env, ts[1])) > int(self.expr(env, ts[2])):
                self._goto_label(env, lbl, ts[3])
        elif cmd == 'ife':
            if not self._compare(self.expr(env, ts[1]), self.expr(env, ts[2])):
                self._goto_if_false(program, env)
        elif cmd == 'ifg':
            if self.expr(env, ts[1]) <= self.expr(env, ts[2]):
                self._goto_if_false(program, env)
        elif cmd == 'els':
            self._goto_if_end(program, env)
        elif cmd == 'fin':
            return


        # === ARITHMATIC ===
        elif cmd == 'add':
            var = ts[1]
            v1 = self.expr(env, ts[2])
            v2 = self.expr(env, ts[3])
            if v1 is None and self._is_numeric(v2):
                self._assign(env, var, chr(v2))
            else:
                if type(v1) == str or type(v2) == str:
                    v1, v2 = str(v1), str(v2)
                self._assign(env, var, v1 + v2)
        elif cmd == 'sub':
            var = ts[1]
            v1 = self.expr(env, ts[2])
            v2 = self.expr(env, ts[3])
            if type(v1) == str and v2 is None:
                self._assign(env, var, ord(v1))
            else:
                self._assign(env, var, v1 - v2)
        elif cmd == 'mul':
            var = ts[1]
            v1 = self.expr(env, ts[2])
            v2 = self.expr(env, ts[3])
            if type(v1) == str and type(v2) == int and v2 > 0:
                # same behavior as Python
                self._assign(env, var, v1 * v2)
            else:
                self._assign(env, var, int(v1) * int(v2))
        elif cmd == 'mod':
            var = ts[1]
            v1 = self.expr(env, ts[2])
            v2 = self.expr(env, ts[3])
            self._assign(env, var, v1 % v2)
        elif cmd == 'div':
            var = ts[1]
            v1 = self.expr(env, ts[2])
            v2 = self.expr(env, ts[3])
            self._assign(env, var, v1 // v2)

        # === DATA TYPE ===
        elif cmd == 'int':
            param = self.expr(env, ts[2])
            res = None
            if self._is_numeric(param):
                res = int(param)
            self._assign(env, ts[1], res)
        elif cmd == 'str':
            val = self.expr(env, ts[2])
            self._assign(env, ts[1], str(val))
        elif cmd == 'typ':
            val = self.expr(env, ts[2])
            t = 'err'
            if type(val) == int:
                t = 'int'
            elif type(val) == str:
                t = 'str'
            elif type(val) == list:
                t = 'list'
            elif type(val) == dict:
                t = 'map'
            elif val is None:
                t = 'nil'
            self._assign(env, ts[1], t)
            #print(type(val))


        # === LIST ===
        elif cmd == 'psh':
            list_var = ts[1][1:] # remove $
            list_val = self._get_var_val(env, list_var)
            for val in ts[2:]:
                if type(list_val) == str:
                    # string
                    v = self.expr(env, val)
                    self._assign(env, list_var, list_val + v)
                    list_val = self._get_var_val(env, list_var)
                else:
                    # list
                    list_val.append(self.expr(env, val))
        elif cmd == 'pop':
            list_var = ts[1][1:] # remove $
            list_val = self._get_var_val(env, list_var)
            var_name = ts[2]
            if type(list_val) == str:
                # string
                if len(list_val) == 0:
                    self._assign(env, var_name, '')
                else:
                    self._assign(env, var_name, list_val[-1])
                    self._assign(env, list_var, list_val[:-1])
            else:
                # list
                val = list_val.pop() if list_val else None
                self._assign(env, var_name, val)
        elif cmd == 'pol':
            list_var = ts[1][1:] # remove $
            list_val = self._get_var_val(env, list_var)
            var_name = ts[2]
            if type(list_val) == str:
                # string
                if len(list_val) == 0:
                    self._assign(env, var_name, '')
                else:
                    self._assign(env, var_name, list_val[0])
                    self._assign(env, list_var, list_val[1:])
            elif type(list_val) == list:
                # list
                if len(list_val) == 0:
                    self._assign(env, var_name, None)
                else:
                    self._assign(env, var_name, list_val[0])
                    self._assign(env, list_var, list_val[1:])
            else:
                print('ERR cannot pol data type: ', type(list_val), ' line:', env['pc']+1)
        elif cmd == 'len':
            list_var = ts[1][1:] # remove $
            list_val = self._get_var_val(env, list_var)
            var_name = ts[2]
            # list, dict, str
            self._assign(env, var_name, len(list_val))


        # === MAP ===
        elif cmd == 'put':
            map_var_name = ts[1][1:]
            map_var_val = self._get_var_val(env, map_var_name)
            map_key = self.expr(env, ts[2])
            map_val = self.expr(env, ts[3])
            if type(map_var_val) == str:
                map_var_val = map_var_val[0:map_key] + map_val + map_var_val[map_key+1:]
                self._assign(env, map_var_name, map_var_val)
            else:
                map_var_val[map_key] = map_val
        elif cmd == 'get':
            map_var_name = ts[1][1:]
            map_var_val = self._get_var_val(env, map_var_name)
            map_key = self.expr(env, ts[2])
            if type(map_var_val) == dict:
                # map
                map_val_by_key = map_var_val.get(map_key)
            else:
                # str and list
                if map_key < len(map_var_val):
                    map_val_by_key = map_var_val[map_key]
                else:
                    map_val_by_key = None
                if type(map_var_val) == str and map_val_by_key is None:
                    map_val_by_key = ''
            self._assign(env, ts[3], map_val_by_key)
        elif cmd == 'key':
            map_var_name = ts[1][1:]
            map_var_val = self._get_var_val(env, map_var_name)
            self._assign(env, ts[2], list(map_var_val.keys()))
        elif cmd == 'del':
            map_var_name = ts[1][1:]
            map_key = self.expr(env, ts[2])
            map_var_val = self._get_var_val(env, map_var_name)
            del map_var_val[map_key]


        # === MISC ===
        elif cmd == 'rnd':
            a, b = self.expr(env, ts[2]), self.expr(env, ts[3])
            val = random.randint(a, b)
            self._assign(env, ts[1], val)
        elif cmd == 'tim':
            time_type = self.expr(env, ts[2])
            today = datetime.date.today()
            now = datetime.datetime.now()
            val = -1
            if time_type == 'year':
                val = today.year
            elif time_type == 'month':
                val = today.month
            elif time_type == 'date':
                val = today.day
            elif time_type == 'day':
                val = today.isoweekday()
            elif time_type == 'hour':
                val = now.hour
            elif time_type == 'minute':
                val = now.minute
            elif time_type == 'second':
                val = now.second
            elif time_type == 'milli':
                val = time.time_ns() % 10**9 // 10**6
            elif time_type == 'now':
                val = time.time_ns() // 10**6
            self._assign(env, ts[1], val)
        elif cmd == 'slp':
            time.sleep(self.expr(env, ts[1]) / 1000)

        # === FUNC ===
        elif cmd == 'def':
            self._goto_end(program, env, 'end')
        elif cmd in ('ret', 'end'):
            val = None  # return None by default
            if len(ts) > 1:
                val = self.expr(env, ts[1])
            stack_obj = env['stack'].pop()
            if cmd == 'ret':
                self._assign(env, 'ret', val)
            env['pc'] = stack_obj['pc']
        elif cmd == 'cal':
            func_name = ts[1]
            args = ts[2:]
            func_env = {}
            for i, v in enumerate(args):
                func_env[str(i)] = self.expr(env, v)
            env['stack'].append({
                'func': func_name,
                'pc': env['pc'],
                'env': func_env
                })
            env['pc'] = fun[func_name]


        # === FOR LOOP ===
        elif cmd == 'for':
            var = ts[1]
            rg = self.expr(env, ts[2])
            if var not in env['loops']:
                # init a new loop state
                rg_list = []
                if type(rg) == int:
                    rg_list = list(range(rg))
                elif type(rg) == list:
                    rg_list = rg
                elif type(rg) == str:
                    rg_list = list(rg)
                elif type(rg) == dict:
                    rg_list = list(rg.keys())
                env['loops'][var] = {
                    'items': rg_list,
                    'pc': env['pc'],
                    'index': 0,
                }

            loop_state = env['loops'][var]
            items = loop_state['items']
            index = loop_state['index']
            if index >= len(items):
                del env['loops'][var]
                self._goto_loop_end(program, env)
            else:
                self._assign(env, var, items[index])
                loop_state['index'] += 1
        elif cmd == 'nxt':
            self._back_to_loop_head(program, env)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 runtime.py <input_file> [<output-device>]')
        sys.exit(1)
    
    output_device = None
    if len(sys.argv) >= 3:
        output_device = sys.argv[2]

    parser = Parser()
    evaluator = Evaluator(output_device=output_device)
    env = {
        'pc': 0,
        'stack': [],
        'global': {},
        'loops': {},
    }

    with open(sys.argv[1], 'r') as src_file:
        prog, lbls, funcs = parser.parse(src_file.read())
        while env['pc'] < len(prog):
            evaluator.eval(prog[env['pc']], env, lbls, funcs, prog)
            env['pc'] += 1