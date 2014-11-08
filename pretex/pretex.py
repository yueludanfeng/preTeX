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
\\vec\{[^\$\{\}]+\} #\vec{abc}.. b. no nested {} because that's impossible in regex
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

re_int_sum = re.compile(r"""
(?<=\\)
(?P<symbol>sum|prod|int|iint|iiint|idotsint|oint)
\ *?_\ *?
(?P<arg_1>[^\ \n$]+)
\ *\^\ *
(?P<arg_2>[^\ \n$]+)
(?=$|\ |\n|,)
""", re.VERBOSE)

re_frac = re.compile(r"""
(?<=\\frac)
\ +?
(?P<nom>[^\ \{\}\n\$]+?)
\ +?
(?P<denom>[^\ \{\}\n\$]+?)
(?=$|\ |\n|,)
""", re.VERBOSE)

re_cdot = re.compile(r"""
(?P<before>.)(?<!\^)\*(?P<after>.)
""", re.VERBOSE)

re_dots = re.compile(r"""
(?P<before>[^\.])\.\.\.(?P<after>[^\.])
""", re.VERBOSE)

re_braket_separate = re.compile(r"""
<
(?P<bra_content>[^\|<>]+)
\|
(?P<middle_content>[^\|<>]+)
\|
(?P<ket_content>[^\|<>]+)
>
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


def transform_math(math_string):
    def repl_dots(matchobj):
        return "{before}{command}{{{content}}}".format(before=matchobj.group('before'),
                                                       command=r"\dot" if matchobj.group(
                                                           'dot_type') == "." else r"\ddot",
                                                       content=matchobj.group('content'))

    trafo_count = dict()
    transformations = [("dot_special", re_dot_special, repl_dots),
                       ("dot_normal", re_dot_normal, repl_dots),
                       ("int_sum", re_int_sum, r"\g<symbol>_{\2}^{\3}"),
                       ("frac", re_frac, r"{\g<nom>}{\g<denom>}"),
                       ("cdot", re_cdot, r"\g<before>\cdot \g<after>"),
                       ("dots", re_dots, r"\g<before>\dots \g<after>"),
                       ("braket", re_braket, r"\\braket{\1}")]
    for name, pattern, repl in transformations:
        math_string, trafo_count[name] = re.subn(pattern, repl, math_string)
    # print("replacements in {s}: {count}".format(s=match_content, count=str(trafo_count)))
    return math_string


def replace_math_outer(math_outer_old):
    def replace_math_inner(match_obj_123):
        return "{env_opening}{dm}{transformed}{env_closing}".format(
            dm="\displaystyle " if match_obj_123.group("prefix") == "d" else "",
            env_opening=match_obj_123.group("env_opening"),
            transformed=transform_math(math_string=match_obj_123.group("env_content")),
            env_closing=match_obj_123.group("env_closing")
        )

    re_extract_math = re.compile(r"""
(?P<prefix>(?<=\ )d|)
(?P<env_opening>
  \$|
  \\begin\ *?{(?P<env_name>(?:equation|align|eqnarray|gather|flalign|multiline|alignat)\*?)}
)
(?P<env_content>[^\$]+?)
(?P<env_closing>
  \$|
  \\end\ *?{(?P=env_name)}
)
        """, re.VERBOSE)

    string_new = re.sub(re_extract_math, repl=replace_math_inner, string=math_outer_old)
    return string_new


def parse_filenames(parameters):
    def filename_sanitizer(filename):
        if "." not in filename:
            raise argparse.ArgumentTypeError("String '{s}' does not match required format".format(s=filename))
        return filename

    parser = argparse.ArgumentParser()
    parser.add_argument("input_filename", type=filename_sanitizer, help="pyth to file input")
    parser.add_argument("-o", "--output", dest="output_filename", type=filename_sanitizer, help="output file")
    args = parser.parse_args(parameters)

    if args.output_filename:
        output_filename = args.output_filename
    else:
        dot_position = args.input_filename.rfind(".")
        output_filename = args.input_filename[:dot_position] + "_t" + args.input_filename[dot_position:]

    if args.input_filename == output_filename:
        raise ValueError("Output and input file are same. You're a crazy person! Abort!!!")
    return args.input_filename, output_filename


def main():
    input_filename, output_filename = parse_filenames(parameters=sys.argv[1:])
    with io.open(input_filename, 'r', encoding='utf-8') as file_read:
        file_content = file_read.read()

    file_content = replace_math_outer(math_outer_old=file_content)

    with io.open(output_filename, 'w', encoding='utf-8') as file_out:
        file_out.write(file_content)


if __name__ == "__main__":
    main()