r"""
Simple python preprocessor.

All keywords are on a new line beginning with "##", followed by any number of
whitespace chars and the keyword, optionally followed by arguments.

Names
Definitions can be anything the regular expression "\w+" can match.

Expressions
Expressions are evaluated in python with current definitions plus python
builtins. In-place operations with definition are not currently possible.

Supported keywords (signification should be straightforward):
  IF expr
  IFDEF name
  IFNDEF name
  ELIF expr
  ELSE
  ENDIF
  DEFINE name[=expr]
  UNDEF[INE] name

NOTE: There is NO SUBSTITUTION support, and none is planned. You can just
execute any substitution you wish in the code calling preprocess(). Hence
definition names will not cause any conflict with code.

Test case

>>> from cStringIO import StringIO
>>> code = '''\
... ##IFNDEF baz # This is a comment
... ##  DEFINE baz = 1 + 1 # Another comment
... ##ELSE
... ##  DEFINE baz = baz + 1
... ##ENDIF
... ##IFDEF foo
... print 'foo'
... ##UNDEF foo
... ##ELSE
... print 'bar'
... ##ENDIF
... ##IF baz > 2 # Yet another comment
... print 'baz'
... ##ENDIF
... '''

First run, with empty variable definition.

>>> out = StringIO()
>>> defines = {}
>>> preprocess(StringIO(code), out, defines=defines)
>>> out.getvalue()
"print 'bar'\n"
>>> defines['baz']
2

Second run, reusing the same set of variable definition and defining "foo".

>>> defines['foo'] = None
>>> out = StringIO()
>>> preprocess(StringIO(code), out, defines=defines)
>>> out.getvalue()
"print 'foo'\nprint 'baz'\n"
>>> defines['baz']
3
>>> 'foo' in defines
False
"""
import re

# Note: should ideally be written as a tokeniser and a grammar, but I intend
# to use it to preprocess a parser...

_PREFIX = re.compile(r'^##\s*(.+)').match
_IF = re.compile(r'IF\s+(.+)').match
_ELIF = re.compile(r'ELIF\s+.+').match
_ELSE = re.compile(r'ELSE\b').match
_ENDIF = re.compile(r'ENDIF\b').match
_DEFINE = re.compile(r'DEFINE\s+(\w+)\s*(?:=\s*(.+))?').match
_UNDEF = re.compile(r'UNDEF(?:INE)?\s+(\w+)').match
_IFDEF = re.compile(r'IFDEF\s+(\w+)').match
_IFNDEF = re.compile(r'IFNDEF\s+(\w+)').match

class PreprocessorError(Exception):
    """
    Raised when there are preprocessor syntax errors in input.
    """
    pass

def preprocess(infile, outfile, defines=None):
    """
    infile
        File-like object, opened for reading.
    outfile
        File-like object, opened for writing.
    defines
        Mapping of values to start preprocessing with.
        Note: This mapping will be modified during file preprocessing.
    """
    def _eval(expression):
        my_globals = defines.copy()
        my_globals['__builtins__'] = __builtins__
        return eval(expression, my_globals)
    def enter():
        stack.append((emit, lineno))
    stack = []
    emit = True
    if defines is None:
        defines = {}
    for lineno, line in enumerate(infile.readlines(), 1):
        directive = _PREFIX(line)
        if directive is not None:
            line = directive.group(1)
            if _IF(line) is not None:
                enter()
                emit = stack[-1][0] and _eval(_IF(line).group(1))
            elif _ELIF(line) is not None:
                if not stack:
                    raise PreprocessorError('%i: Unexpected conditional block '
                        'continuation' % (lineno, ))
                if not emit:
                    emit = stack[-1][0] and _eval(_ELIF(line).group(1))
            elif _ELSE(line) is not None:
                if not stack:
                    raise PreprocessorError('%i: Unexpected conditional block '
                        'continuation' % (lineno, ))
                emit = stack[-1][0] and not emit
            elif _ENDIF(line) is not None:
                if not stack:
                    raise PreprocessorError('%i: Unexpected conditional block '
                        'continuation' % (lineno, ))
                try:
                    emit, _ = stack.pop()
                except IndexError:
                    raise PreprocessorError('%i: Unexpected conditional block '
                        'end' % (lineno, ))
            elif _IFDEF(line) is not None:
                enter()
                emit = stack[-1][0] and _IFDEF(line).group(1) in defines
            elif _IFNDEF(line) is not None:
                enter()
                emit = stack[-1][0] and _IFNDEF(line).group(1) not in defines
            elif _DEFINE(line) is not None:
                if emit:
                    groups = _DEFINE(line).groups()
                    if len(groups) == 1:
                        value = None
                    else:
                        value = _eval(groups[1])
                    defines[groups[0]] = value
            elif _UNDEF(line) is not None:
                if emit:
                    del defines[_UNDEF(line).group(1)]
            else:
                raise PreprocessorError('%i: Unknown directive %r' % (lineno,
                    directive))
            continue
        if emit:
            outfile.write(line)
    if stack:
        raise PreprocessorError('Blocks still open at end of input (block '
            'starting line): %r' % (stack, ))

if __name__ == "__main__":
    import doctest
    doctest.testmod()

