import lark

grammaire = lark.Lark("""
variables : IDENTIFIANT (","  IDENTIFIANT)*
expr : IDENTIFIANT -> variable | NUMBER -> nombre | expr OP expr -> binexpr | "(" expr ")" -> parenexpr | IDENTIFIANT "(" (expr ",")* expr ")" -> call_function | IDENTIFIANT "(" ")" -> call_function_no_arg | "'" string "'" -> str | "'" "'" -> empty_str | element -> elt | IDENTIFIANT ".length" -> length_tableau | "*" IDENTIFIANT -> call_value | "&" IDENTIFIANT -> call_pointeur
cmd : IDENTIFIANT "=" expr ";"-> assignment|"while" "(" expr ")" "{" bloc "}" -> while | "if" "(" expr ")" "{" bloc "}" -> if | "printf" "(" expr ")" ";"-> printf | element "=" expr ";" -> assignment_tableau | IDENTIFIANT "=" "new" tableau ";" -> creation_tableau
bloc : (cmd)*
prog : functions "main" "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
functions : function*
function : IDENTIFIANT "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
string : /[a-zA-Z0-9][a-zA-Z0-9]*/
tableau : "int" "[" expr "]"
element : IDENTIFIANT "[" expr "]"  
NUMBER : /[0-9]+/
OP : /[+\*>-]/
IDENTIFIANT : /[a-zA-Z][a-zA-Z0-9]*/
%import common.WS
%ignore WS
""", start = "prog")

cpt = iter(range(10000))
op2asm = {"+" : "add rax, rbx","-" : "sub rax, rbx"}

########################################## Pretty Printer ##############################################################

def pp_variables(vars):
    return ", ".join([t.value for t in vars.children])

def pp_expr(expr):
    if expr.data in {"variable", "nombre"}:
        return expr.children[0].value
    elif expr.data == "binexpr":
        e1 = pp_expr(expr.children[0])
        e2 = pp_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e1} {op} {e2}"
    elif expr.data == "parenexpr":
        return f"({pp_expr(expr.children[0])})"
    elif expr.data == "call_function":
        nom = expr.children[0]
        vars = ", ".join([pp_expr(ex) for ex in expr.children[1:]])
        return f"{nom} ({vars})"
    elif expr.data == "call_function_no_arg":
        nom = expr.children[0]
        return f"{nom} ()"
    elif expr.data=="str":
        return(pp_string(expr.children[0]))
    elif expr.data=="empty_str":
        return "''"
    elif expr.data=="tbl":
        return(f"new {pp_tableau(expr.children[0])}")
    elif expr.data=="elt":
        return(pp_element(expr.children[0]))
    elif expr.data=="call_value":
        return(f"*{expr.children[0].value}")
    elif expr.data=="call_pointeur":
        return(f"&{expr.children[0].value}")
    else:
        raise Exception("Not implemented")

def pp_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = pp_expr(cmd.children[1])
        return f"{lhs} = {rhs};"
    elif cmd.data == "printf":
        return f"printf( {pp_expr(cmd.children[0])} );"
    elif cmd.data in {"while", "if"}:
        e = pp_expr(cmd.children[0])
        b = pp_bloc(cmd.children[1])
        return f"{cmd.data} ({e}) {{ {b}}}"
    elif cmd.data=="assignment_tableau":
        element=pp_element(cmd.children[0])
        valeur=pp_expr(cmd.children[1])
        return f"{element}={valeur};"
    else:
        raise Exception("Not implemented")

def pp_bloc(bloc):
    return "\n".join([pp_cmd(t) for t in bloc.children])

def pp_function(f):
    nom = f.children[0]
    vars = pp_variables(f.children[1])
    bloc = pp_bloc(f.children[2])
    ret = pp_expr(f.children[3])
    return f"{nom} ({vars}){{ {bloc} return ({ret});}}"

def pp_string(s):
    nom = s.children[0]
    return f"'{nom}'"

def pp_tableau(T):
    taille=pp_expr(T.children[0])
    return f"int [{taille}]"

def pp_element(e):
    nom=e.children[0]
    indice=pp_expr(e.children[1])
    return f"{nom}[{indice}]"

def pp_prg(prog):
    functions="\n\n".join([pp_function(f) for f in prog.children[0].children])
    vars = pp_variables(prog.children[1])
    bloc = pp_bloc(prog.children[2])
    ret = pp_expr(prog.children[3])
    return f"{functions}\n\nmain ({vars}){{ {bloc} return ({ret});}}"

def var_list(ast):
    if isinstance(ast, lark.Token):
        if ast.type == "IDENTIFIANT":
            return {ast.value}
        else:
            return set()
    s = set()
    for c in ast.children:
        s.update(var_list(c))
    return s

  
############################################### COMPILE ###############################################################################

def compile(prg):
    with open("moule.asm") as f:
        code = f.read()
        vars_decl =  "\n".join([f"{x} : dq 0" for x in var_list(prg)])
        code = code.replace("VAR_DECL", vars_decl)
        code = code.replace("VAR_INIT", compile_vars(prg.children[1]))
        code = code.replace("BODY", compile_bloc(prg.children[2]))
        code = code.replace("RETURN", compile_expr(prg.children[3]))
    with open("prgm.asm",'w') as f:
        f.write(code)    
    return code

def compile_expr(expr):
    if expr.data == "variable":
        return f"mov rax, [{expr.children[0].value}]"
    elif expr.data == "nombre":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "binexpr":
        e1 = compile_expr(expr.children[0])
        e2 = compile_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[op]}"
    elif expr.data == "parenexpr":
        return compile_expr(expr.children[0])
    elif expr.data == "elt":
        elt = expr.children[0]
        name = elt.children[0].value
        i = compile_expr(elt.children[1])
        i_bin = f"{i}\npush rax\nmov rax, 1\npop rbx\nadd rax, rbx\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx" # i+1
        return f"{i_bin}\npush rax\nmov rax, {name}\npop rbx\nadd rbx, rax\nmov rax, [rbx]"
    elif expr.data == "length_tableau":
        name = expr.children[0].value
        return f"mov rax, [{name}]"
    elif expr.data == "call_value":
        return f"mov rbx, [{expr.children[0].value}]\nmov rax, [rbx]"
    elif expr.data == "call_pointeur":
        return f"mov rax, {expr.children[0].value}"
    else:
        raise Exception("Not implemented")

def compile_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = compile_expr(cmd.children[1])
        return f"{rhs}\nmov [{lhs}], rax"
    elif cmd.data == "while":
        e = compile_expr(cmd.children[0])
        b = compile_bloc(cmd.children[1])
        index = next(cpt)
        return f"debut{index}:\n{e}\ncmp rax, 0\njz fin{index}\n{b}\njmp debut{index}\nfin{index}:\n"
    elif cmd.data == "assignment_tableau":
        elt = cmd.children[0]
        name = elt.children[0].value
        i = compile_expr(elt.children[1])
        i_bin = f"{i}\npush rax\nmov rax, 1\npop rbx\nadd rax, rbx\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx" #i+1
        lhs = f"{i_bin}\npush rax\nmov rax, {name}\npop rbx\nadd rax, rbx"
        rhs = compile_expr(cmd.children[1])
        return f"{lhs}\npush rax\n{rhs}\npop rbx\nmov [rbx], rax"
    elif cmd.data == "creation_tableau":
        name = cmd.children[0].value
        tbl = cmd.children[1]
        length = compile_expr(tbl.children[0])
        len_bin = f"{length}\npush rax\nmov rax, 1\npop rbx\nadd rax, rbx\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx" #len+1
        return f"{len_bin}\nmov rdi, rax\nextern malloc\ncall malloc\nmov [{name}], rax\n{length}\nmov [{name}], rax"
    else:
        raise Exception("Not implemented")

def compile_bloc(bloc):
    return "\n".join([compile_cmd(t) for t in bloc.children])

def compile_vars(ast):
    s = ""
    for i in range(len(ast.children)):
        s += f"mov rbx, [rbp-0x10]\nmov rdi,[rbx+{8*(i+1)}]\ncall atoi\
            \nmov [{ast.children[i].value}],rax\n"
    return s


############################################### Execution ###############################################################################

import sys
import os

def main(usage, C_file):
    with open(C_file) as f:
        code = f.read()
        prg = grammaire.parse(code)
    if usage == "pp":
        print(pp_prg(prg))
    elif usage == "cp":
        print(compile(prg))
        os.system('nasm -f elf64 prgm.asm')
        os.system('gcc -o prgm prgm.o -no-pie -fno-pie')

if __name__ == '__main__':
    [usage, C_file] = sys.argv[1:]
    sys.exit(main(usage, C_file))
