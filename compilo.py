import lark

grammaire = lark.Lark("""
variables : IDENTIFIANT (","  IDENTIFIANT)*
expr : IDENTIFIANT -> variable | NUMBER -> nombre | expr OP expr -> binexpr | "(" expr ")" -> parenexpr | IDENTIFIANT "(" (expr ",")* expr ")" -> call_function | IDENTIFIANT "(" ")" -> call_function_no_arg | "'" string "'" -> str | "'" "'" -> empty_str | element -> elt | "new" tableau -> tbl 
cmd : IDENTIFIANT "=" expr ";"-> assignment|"while" "(" expr ")" "{" bloc "}" -> while | "if" "(" expr ")" "{" bloc "}" -> if | "printf" "(" expr ")" ";"-> printf | element "=" expr ";" -> assignment_tableau
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

if __name__ == "__main__":
    prg = grammaire.parse("""
    main(Z,T) {
    T=new int[5];
    T[0]=2;
    T[1]=3;
    T[4]=T[1]-T[0];
    T2=new int[2];
    T2[0]=1;
    T2[1]=T2[0];
    Z=T[4]+T2[1];
    return(Z);}""")

############################################### COMPILE ###############################################################################

def compile(prg):
    with open("moule.asm") as f:
        code = f.read()
        vars_decl =  "\n".join([f"{x} : dq 0" for x in var_list(prg)])
        code = code.replace("VAR_DECL", vars_decl)
        code = code.replace("RETURN", compile_expr(prg.children[3]))
        code = code.replace("BODY", compile_bloc(prg.children[2]))
        code = code.replace("VAR_INIT", compile_vars(prg.children[1]))
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
    elif expr.data == "tbl":
        tbl = expr.children[0]
        len = compile_expr(tbl.children[0])
        len_bin = f"{len}\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx"
        return f"{len_bin}\nmov rdi, rax\nextern malloc\ncall malloc"
    elif expr.data == "elt":
        elt = expr.children[0]
        name = elt.children[0].value
        i = compile_expr(elt.children[1])
        i_bin = f"{i}\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx"
        return f"{i_bin}\npush rax\nmov rax, {name}\npop rbx\nadd rbx, rax\nmov rax, [rbx]"
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
        i_bin = f"{i}\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx"
        lhs = f"{i_bin}\npush rax\nmov rax, {name}\npop rbx\nadd rbx, rax\nmov rax, rbx"
        rhs = compile_expr(cmd.children[1])
        return f"{lhs}\npush rax\n{rhs}\npop rbx\nmov [rbx], rax"
    else:
        raise Exception("Not implemented")


def compile_bloc(bloc):
    return "\n".join([compile_cmd(t) for t in bloc.children])

def compile_vars(ast):
    s = ""
    for i in range(len(ast.children)):
        s += f"mov rbx, [rbp-0x10]\nlea rdi,[rbx-{8*(i+1)}]\ncall atoi\
            \nmov [{ast.children[i].value}],rax\n"
    return s

print(compile(prg))