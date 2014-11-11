# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import sys
import argparse
import io

re_dot_special = re.compile(r"""
(?P<before>^|\ |\n|\(|\{)
(?P<content>
\\\w+?|             #\word.. b
\\vec\ \w|          #\vec p.. b
\\vec\{[^\{\}]+\} #\vec{abc}.. b. no nested {} because that's impossible in regex
)
(?P<dot_type>\.|\.\.)
(?=$|\ |\n|,|\)|\})
""", re.VERBOSE)

re_dot_normal = re.compile(r"""
(?P<before>^|\ |\n|\(|\{)
(?P<content>\w+?)
(?P<dot_type>\.|\.\.)
(?=$|\ |\n|,|\)|\})
""", re.VERBOSE)

re_frac = re.compile(r"""
(?<=\\frac)
\ +?
(?P<nom>[^\ \{\}\n]+?)
\ +?
(?P<denom>[^\ \{\}\n]+?)
(?=$|\ |\n|,)
""", re.VERBOSE)

re_cdot = re.compile(r"""
(?<!\^)           # no ^ before to save complex conjugation
\*                # the *
(?P<wspace>\ *)   # whitespace
(?P<after>[\w\\]) # alphanum + \ for greek letters
""", re.VERBOSE)

re_dots = re.compile(r"""
(?<!\.)           # no dot before
\.{3}             # ...
(?!\.)            # no dot after
(?P<wspace>\ *)   # whitespace
(?P<after>.)      # what comes after
""", re.VERBOSE)

re_braket = re.compile(r"""
<(
[^\|<>]+
\|
[^\|<>]+
\|
[^\|<>]+
)>
""", re.VERBOSE)

re_frac_compact = re.compile(r"""
(?P<before>^|\ |\n|\(|\{)
(?P<nom>[^\ ]+?)
\ *//\ *
(?P<denom>[^\ ]+?)
(?P<after>$|\ |\n|\)|\})
""", re.VERBOSE)

re_sub_superscript = re.compile(r"""
(?P<operator>[_\^]) #_
(?P<before>\ *?)   #whitespace
(?P<content>(?:
   [a-zA-Z0-9+\-\*=]| #alphanum, +-*=
  ,[a-zA-Z0-9]        #or comma, but only if followed by alphanum
  ){2,}) #alphanum, comma, +-*
(?P<after>
  $|\ |\n|\)|\}
)
""", re.VERBOSE)


def transform_math(math_string, excluded_commands=None, env_type=None):
    """ the actual transformations with the math contents """
    def sanitize_whitespace(ws_string, after=None):
        if ws_string or not ws_string and after==",": #has whitespace or no whitespace but comma following
            return ws_string
        else:
            return " "

    def repl_dot(matchobj):
        if matchobj.group('dot_type') == ".":
            dot_command = r"\dot"
        else:
            dot_command = r"\ddot"
        return "{before}{dot_command}{{{content}}}".format(before=matchobj.group('before'),
                                                           dot_command=dot_command,
                                                           content=matchobj.group('content'))

    def repl_cdot(matchobj):
        whitespace = sanitize_whitespace(matchobj.group('wspace'))
        return r"\cdot{whitespace}{after}".format(whitespace=whitespace, after=matchobj.group('after'))

    def repl_dots(matchobj):
        whitespace = sanitize_whitespace(matchobj.group('wspace'), after=matchobj.group('after'))
        print("dots_whitespace:", [whitespace])
        return r"\dots{whitespace}{after}".format(whitespace=whitespace, after=matchobj.group('after'))

    # RegEx transformations
    if excluded_commands is None:
        excluded_commands = []
    trafo_count = dict()
    re_transformations = [("dot", re_dot_special, repl_dot),
                          ("dot", re_dot_normal, repl_dot),
                          ("frac", re_frac, r"{\g<nom>}{\g<denom>}"),
                          ("cdot", re_cdot, repl_cdot),
                          ("dots", re_dots, repl_dots),
                          ("braket", re_braket, r"\\braket{\1}"),
                          ("frac_compact", re_frac_compact, r"\g<before>\\frac{\g<nom>}{\g<denom>}\g<after>"),
                          ("sub_superscript", re_sub_superscript, r"\g<operator>\g<before>{\g<content>}\g<after>")]

    for name, pattern, repl in re_transformations:
        if name not in excluded_commands:
            math_string, trafo_count[name] = re.subn(pattern, repl, math_string)

    # auto_align
    if env_type in ["align", "align*"] and "auto_align" not in excluded_commands:
        if r"\\" not in math_string:
            content_split = [line for line in math_string.split("\n") if line and not line.isspace()]
            math_string = "\n" + " \\\\\n".join(content_split) + "\n"
        lines = math_string.split(r"\\")
        if all(line.count(r"=") == 1 and line.count(r"&=") == 0 for line in lines):
            line_split = [line.split(r"=") for line in lines]
            line_joined = [r"&=".join(l) for l in line_split]
            lines_joined = r"\\".join(line_joined)
            math_string = lines_joined

    # simple transformations
    simple_transformations = [("arrow", r" -> ", r" \to "),
                              ("approx", r"~=", r"\approx"),
                              ("leq", r"<=", r"\leq"),
                              ("geq", r">=", r"\geq"),
                              ("ll", r"<<", r"\ll"),
                              ("gg", r">>", r"\gg"),
                              ("neq", r"!=", r"\neq")]
    single_backslash = r"\ "[0]
    for name, source, target in simple_transformations:
        if name not in excluded_commands:
            needs_whitespace = single_backslash in target and target[-1] != " "
            if needs_whitespace:
                if source+" " in math_string:
                    source += " "
                    target += " "
                else:
                    target += " "
            math_string = math_string.replace(source, target)

    return math_string


def replace_math_outer(math_outer_old, excluded_commands=None):
    """ passes the inside between math delimiters to transform_math() and wraps it in their original delimiters  """
    def replace_math_inner(match_obj):
        return "{env_opening}{dm}{transformed}{env_closing}".format(
            dm="\displaystyle " if match_obj.group("prefix") == "d" else "",
            env_opening=match_obj.group("env_opening"),
            transformed=transform_math(math_string=match_obj.group("env_content"), excluded_commands=excluded_commands,
                                       env_type=match_obj.group("env_name")),
            env_closing=match_obj.group("env_closing")
        )

    re_extract_math = re.compile(r"""
(?P<prefix>(?<=\ )d|)
(?P<env_opening>
  \$\$|
  \$|
  \\\(|
  \\\[|
  \\begin\ *?{(?P<env_name>
    (?:
      equation|align|math|displaymath|eqnarray|gather|flalign|multiline|alignat
    )
    \*
  ?)}
)
(?P<env_content>
  (?:\n|\\\$|.)+?
)
(?P<env_closing>
  (?P=env_opening)|
  \\end\ *?{(?P=env_name)}
)
        """, re.VERBOSE)

    string_new = re.sub(re_extract_math, repl=replace_math_inner, string=math_outer_old)
    return string_new


def parse_cmd_arguments(parameters):
    """ returns a tuple of input-, output-filename and list of excluded commands. optional parameters default to None """

    def filename_sanitizer(filename):
        if "." not in filename:
            raise argparse.ArgumentTypeError("String '{s}' does not match required format".format(s=filename))
        return filename

    parser = argparse.ArgumentParser()
    parser.add_argument("input_filename", type=filename_sanitizer, help="pyth to file input")
    parser.add_argument("-o", "--output", dest="output_filename", type=filename_sanitizer, help="output file")
    parser.add_argument("-s", "--skip", dest="excluded_commands", action='append',
                        help="comma seperated list of transformations to exclude")
    args = parser.parse_args(parameters)

    if args.output_filename:
        output_filename = args.output_filename
    else:
        dot_position = args.input_filename.rfind(".")
        output_filename = args.input_filename[:dot_position] + "_t" + args.input_filename[dot_position:]

    if args.input_filename == output_filename:
        raise ValueError("Output and input file are same. You're a crazy person! Abort!!!")
    return args.input_filename, output_filename, args.excluded_commands


def main():
    input_filename, output_filename, excluded_commands = parse_cmd_arguments(parameters=sys.argv[1:])
    with io.open(input_filename, 'r', encoding='utf-8') as file_read:
        file_content = file_read.read()

    file_content = replace_math_outer(file_content, excluded_commands)

    with io.open(output_filename, 'w', encoding='utf-8') as file_out:
        file_out.write(file_content)


if __name__ == "__main__":
    main() # pragma: no cover