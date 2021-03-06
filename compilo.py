from operator import indexOf
import lark
import sys
import os

grammaire = lark.Lark("""
variables : IDENTIFIANT (","  IDENTIFIANT)*
expr : IDENTIFIANT -> variable | NUMBER -> nombre | expr OP expr -> binexpr | "(" expr ")" -> parenexpr | IDENTIFIANT "(" (expr ",")* expr ")" -> call_function | IDENTIFIANT "(" ")" -> call_function_no_arg | "'" string "'" -> str | "'" "'" -> empty_str | element -> elt | "new" tableau -> tbl | "*" IDENTIFIANT -> call_value | "**" IDENTIFIANT -> call_call_value | "&" IDENTIFIANT -> call_pointeur | "malloc" "(" expr ")" -> malloc
cmd : IDENTIFIANT "=" expr ";"-> assignment|"while" "(" expr ")" "{" bloc "}" -> while | "if" "(" expr ")" "{" bloc "}" -> if | "printf" "(" expr ")" ";"-> printf | element "=" expr ";" -> assignment_tableau | "*" IDENTIFIANT "=" expr ";" -> assignment_pointeur
bloc : (cmd)*
prog : functions "main" "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
functions : (function* function_no_arg*)*
function : IDENTIFIANT "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
string : /[a-zA-Z0-9 ][a-zA-Z0-9 ]*/
tableau : "int" "[" expr "]"
element : IDENTIFIANT "[" expr "]"  
NUMBER : /[0-9]+/
OP : /[+\*>-]/
IDENTIFIANT : /[a-zA-Z][a-zA-Z0-9]*/
%import common.WS
%ignore WS
""", start = "prog")

cpt = iter(range(10000))
op2asm = {"+" : "add rax, rbx", "-" : "sub rax, rbx", "*" : "imul rax, rbx"}

################################.children[0].value########## Pretty Printer ##############################################################

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
        return f"{nom}({vars})"
    elif expr.data == "call_function_no_arg":
        nom = expr.children[0]
        return f"{nom}()"
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
    elif expr.data=="call_call_value":
        return(f"**{expr.children[0].value}")
    elif expr.data=="call_pointeur":
        return(f"&{expr.children[0].value}")
    elif expr.data == "malloc":
        return f"malloc( {pp_expr(expr.children[0])} );"
    else:
        raise Exception("Not implemented")

def pp_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = pp_expr(cmd.children[1])
        return f"{lhs} = {rhs};"
    elif cmd.data == "printf":
        return f"printf({pp_expr(cmd.children[0])});"
    elif cmd.data in {"while", "if"}:
        e = pp_expr(cmd.children[0])
        b = pp_bloc(cmd.children[1])
        return f"{cmd.data}({e}) {{\n{b}\n}}"
    elif cmd.data=="assignment_tableau":
        element=pp_element(cmd.children[0])
        valeur=pp_expr(cmd.children[1])
        return f"{element}={valeur};"
    elif cmd.data=="assignment_pointeur":
        lhs = cmd.children[0].value
        rhs = pp_expr(cmd.children[1])
        return f"*{lhs} = {rhs};"
    else:
        raise Exception("Not implemented")

def pp_bloc(bloc):
    return "\n".join([pp_cmd(t) for t in bloc.children])

def pp_function(f):
    nom = f.children[0]
    vars = pp_variables(f.children[1])
    bloc = pp_bloc(f.children[2])
    ret = pp_expr(f.children[3])
    return f"{nom}({vars}) {{\n{bloc}\nreturn({ret});\n}}"

def pp_string(s):
    nom = s.children[0]
    return f"'{nom}'"

def pp_tableau(T):
    taille=pp_expr(T.children[0])
    return f"int[{taille}]"

def pp_element(e):
    nom=e.children[0]
    indice=pp_expr(e.children[1])
    return f"{nom}[{indice}]"

def pp_prg(prog):
    functions="\n\n".join([pp_function(f) for f in prog.children[0].children])
    vars = pp_variables(prog.children[1])
    bloc = pp_bloc(prog.children[2])
    ret = pp_expr(prog.children[3])
    return f"{functions}\n\nmain({vars}) {{\n{bloc}\nreturn({ret});\n}}"

def var_list(ast):
    if isinstance(ast, lark.Token):
        if ast.type == "IDENTIFIANT":
            return {ast.value}
        else:
            return set()
    s = set()
    for c in ast.children:
        if (isinstance(c, lark.Tree) and (c.data=="call_function" or c.data=="call_function_no_arg")):
            for a in c.children[1:]:
                s.update(var_list(a))
        else:
            s.update(var_list(c))
    return s



############################################### COMPILE ###############################################################################

def compile(prg):
    with open("moule.asm") as f:
        code = f.read()
        vars_decl =  "\n".join([f"{x} : dq 0" for x in var_list(prg.children[2])|var_list(prg.children[1])])
        code = code.replace("VAR_DECL", vars_decl)
        code = code.replace("FUNCTIONS", compile_functions(prg.children[0]))
        code = code.replace("RETURN", compile_expr(prg.children[3]))
        code = code.replace("BODY", compile_bloc(prg.children[2]))
        code = code.replace("VAR_INIT", compile_vars(prg.children[1]))

    with open("prgm.asm",'w') as f:
        f.write(code)    
    return code

def compile_functions(functions):
    res=[]
    for x in functions.children:
        if x.data=="function":
            res.append(compile_function(x))
        if x.data=="function_no_arg":
            res.append(compile_function_no_arg(x))
    return "\n".join(res)
            
def compile_function_no_arg(function):
    ens_local_var=var_list(function.children[1])
    list_local_var=[var for var in ens_local_var]
    res=f"{function.children[0]}:\npush rbp\nmov rbp,rsp\n"
    res+=compile_bloc_for_function(function.children[1],list_local_var,[])+"\n"
    res+=compile_expr_for_function(function.children[2],list_local_var,[])+"\n"
    res+= "mov rsp,rbp\npop rbp\nret"
    return res

def compile_function(function):
    ens_var_input=var_list(function.children[1])
    ens_all_var=var_list(function.children[2])
    ens_local_var=ens_all_var.difference(ens_var_input)
    list_var_input=[var.value for var in function.children[1].children]
    list_local_var=[var for var in ens_local_var]
    res=f"{function.children[0]}:\npush rbp\nmov rbp,rsp\n"
    res+=compile_bloc_for_function(function.children[2],list_local_var,list_var_input)+"\n"
    res+=compile_expr_for_function(function.children[3],list_local_var,list_var_input)+"\n"
    res+= "mov rsp,rbp\npop rbp\nret"
    return res

def compile_expr(expr):
    if expr.data == "variable":
        return f"mov rax, [{expr.children[0].value}]\n"
    elif expr.data == "nombre":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "binexpr":
        if expr.children[2].data=="str":
            n_str=expr.children[2].children[0].children[0].value
            ex="push rcx\n"
            while len(n_str)//8>0:
                ex+=f"pop rcx\npush rax\nadd rax, rcx\nmov rbx, '{n_str[0:8]}'\nmov [rax], rbx\nsub rax, rcx\nmov rdi, rax\ncall strlen\nmov rcx ,rax\npop rax\npush rcx\n"
                n_str=n_str[8:]
            if len(n_str)>0:
                ex+=f"pop rcx\npush rax\nadd rax, rcx\nmov rbx, '{n_str}'\nmov [rax], rbx\nsub rax, rcx\nmov rdi, rax\ncall strlen\nmov rcx ,rax\npop rax"
            e1 = compile_expr(expr.children[0])
            e1+=ex
            return e1  
        e1 = compile_expr(expr.children[0])
        e2 = compile_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[op]}"
    elif expr.data == "parenexpr":
        return compile_expr(expr.children[0])
    elif expr.data == "str" :
        n_str=expr.children[0].children[0].value
        ex="mov rcx, 0\npush rcx\nmov rdi, 64\ncall malloc\n"
        while len(n_str)//8>0:
            ex+=f"pop rcx\npush rax\nadd rax, rcx\nmov rbx, '{n_str[0:8]}'\nmov [rax], rbx\nsub rax, rcx\nmov rdi, rax\ncall strlen\nmov rcx ,rax\npop rax\npush rcx\n"
            n_str=n_str[8:]
        if len(n_str)>0:
            ex+=f"pop rcx\npush rax\nadd rax, rcx\nmov rbx, '{n_str}'\nmov [rax], rbx\nsub rax, rcx\nmov rdi, rax\ncall strlen\nmov rcx ,rax\npop rax"                   
        return ex
    elif expr.data == "call_function":
        push_arg="\n".join([compile_expr(expr.children[i])+"\npush rax" for i in range(len(expr.children)-1,0,-1)])+"\n"
        call_function=f"call {expr.children[0]}"
        pop_arg=f"\nadd rsp,{8*(len(expr.children)-1)}"
        return  push_arg+call_function+pop_arg
    elif expr.data == "call_function_no_arg":
        call_function=f"call {expr.children[0]}"
        return  call_function   
    elif expr.data == "tbl":
        tbl = expr.children[0]
        lenght = compile_expr(tbl.children[0])
        len_bin = f"{lenght}\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx"
        return f"{len_bin}\nmov rdi, rax\ncall malloc"
    elif expr.data == "elt":
        elt = expr.children[0]
        name = elt.children[0].value
        i = compile_expr(elt.children[1])
        i_bin = f"{i}\npush rax\nmov rax, 8\npop rbx\nimul rax, rbx"
        return f"{i_bin}\npush rax\nmov rax, {name}\npop rbx\nadd rbx, rax\nmov rax, [rbx]"
    elif expr.data == "call_value":
        return f"mov rbx, [{expr.children[0].value}]\nmov rax, [rbx]"
    elif expr.data == "call_call_value":
        return compile_expr_for_double_pointeur(expr.children[0].value)
    elif expr.data == "call_pointeur":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "malloc":
        return f"mov edi, {expr.children[0].value}\nextern malloc\ncall malloc"
    else:
        raise Exception("Not implemented")

def compile_cmd(cmd):
    if cmd.data == "assignment":
        if cmd.children[1].data == "str":
            lhs = cmd.children[0].value
            rhs = compile_expr(cmd.children[1])
            return f"{rhs}\nmov [{lhs}], rax\nmov rbx, [fmts]\nmov [fmt], rbx\nmov rax, [{lhs}]"
        else :
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
    elif cmd.data == "assignment_pointeur":
        lhs = cmd.children[0].value
        rhs = compile_expr(cmd.children[1])
        return f"mov [Y], 2"
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

########################################## COMPILE IN POINTEURS ###############################################################################

def compile_expr_for_double_pointeur(value):
    l1=f"mov rax, [{value}]"
    l2=f"mov rbx, [rax]"
    l3=f"mov rax, [rbx]"
    return l1+"\n"+l2+"\n"+l3

########################################## COMPILE IN FUNCTIONS ###############################################################################

def compile_expr_for_function(expr,local_var,global_var):
    if expr.data == "variable":
        if (expr.children[0].value in local_var):
            return f"mov rax, [rbp-{local_var.index(expr.children[0].value)*8+8}]"
        elif (expr.children[0].value in global_var):
            return f"mov rax, [rbp+{global_var.index(expr.children[0].value)*8+16}]"
        else:
            raise Exception("Not var with this name")
    elif expr.data == "nombre":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "binexpr":
        e1 = compile_expr_for_function(expr.children[0],local_var,global_var)
        e2 = compile_expr_for_function(expr.children[2],local_var,global_var)
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[op]}"
    elif expr.data == "parenexpr":
        return compile_expr_for_function(expr.children[0],local_var,global_var)
    elif expr.data == "call_function":
        push_arg="\n".join([compile_expr(expr.children[i])+"\npush rax" for i in range(len(expr.children)-1,0,-1)])+"\n"
        call_function=f"call {expr.children[0]}"
        pop_arg=f"\nadd rsp,{8*(len(expr.children)-1)}"
        return  push_arg+call_function+pop_arg
    elif expr.data == "call_function_no_arg":
        call_function=f"call {expr.children[0]}"
        return  call_function   
    else:
        raise Exception("Not implemented")

def compile_cmd_for_function(cmd,local_var,global_var):
    if cmd.data == "assignment":
        if (cmd.children[0].value in local_var):
            lhs = f"rbp-{local_var.index(cmd.children[0].value)*8+8}"
        elif (cmd.children[0].value in global_var):
            lhs = f"rbp+{global_var.index(cmd.children[0].value)*8+16}"
        else:
            raise Exception("Not var with this name")
        rhs = compile_expr_for_function(cmd.children[1],local_var,global_var)
        return f"{rhs}\nmov [{lhs}], rax"
    # elif cmd.data == "while":
    #     e = compile_expr_for_function(cmd.children[0],local_var,global_var)
    #     b = compile_bloc_for_function(cmd.children[1],local_var,global_var)
    #     index = next(cpt)
    #     return f"debut{index}:\n{e}\ncmp rax, 0\njz fin{index}\n{b}\njmp debut{index}\nfin{index}:\n"
    else:
        raise Exception("Not implemented")

def compile_bloc_for_function(bloc,local_var,global_var):
    return "\n".join([compile_cmd_for_function(t,local_var,global_var) for t in bloc.children])



############################################### EXECUTE ###############################################################################

def main(usage, C_file):
    with open(C_file) as f:
        code = f.read()
        prg = grammaire.parse(code)
    if usage == "pp":
        print(pp_prg(prg))
    elif usage == "cp":
        compile(prg)
        os.system('nasm -f elf64 prgm.asm')
        os.system('gcc -o prgm prgm.o -no-pie -fno-pie')

if __name__ == '__main__':
    [usage, C_file] = sys.argv[1:]
    sys.exit(main(usage, C_file))