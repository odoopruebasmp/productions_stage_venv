import sys
from openerp.tools import safe_eval
from openerp.tools.safe_eval import _import
from openerp.tools.safe_eval import _SAFE_OPCODES
from openerp.tools.safe_eval import test_expr
from openerp.tools.safe_eval import _import
from openerp.tools.safe_eval import _SAFE_OPCODES
from openerp.tools.safe_eval import test_expr
from openerp.tools.translate import _
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from opcode import HAVE_ARGUMENT, opmap, opname
from types import CodeType
import logging
import openerp
from calendar import monthrange

def safe_eval_expand(expr, globals_dict=None, locals_dict=None, mode="eval", nocopy=False):
    """safe_eval(expression[, globals[, locals[, mode[, nocopy]]]]) -> result

    System-restricted Python expression evaluation

    Evaluates a string that contains an expression that mostly
    uses Python constants, arithmetic expressions and the
    objects directly provided in context.

    This can be used to e.g. evaluate
    an OpenERP domain expression from an untrusted source.

    Throws TypeError, SyntaxError or ValueError (not allowed) accordingly.

    >>> safe_eval("__import__('sys').modules")
    Traceback (most recent call last):
    ...
    ValueError: opcode LOAD_NAME not allowed

    """
    if isinstance(expr, CodeType):
        raise ValueError("safe_eval does not allow direct evaluation of code objects.")

    if '__subclasses__' in expr:
        raise ValueError('expression not allowed (__subclasses__)')

    if globals_dict is None:
        globals_dict = {}

    # prevent altering the globals/locals from within the sandbox
    # by taking a copy.
    if not nocopy:
        # isinstance() does not work below, we want *exactly* the dict class
        if (globals_dict is not None and type(globals_dict) is not dict) \
            or (locals_dict is not None and type(locals_dict) is not dict):
            _logger.warning(
                "Looks like you are trying to pass a dynamic environment, "
                "you should probably pass nocopy=True to safe_eval().")

        globals_dict = dict(globals_dict)
        if locals_dict is not None:
            locals_dict = dict(locals_dict)

    globals_dict.update(
            __builtins__ = {
                '__import__': _import,
                'True': True,
                'False': False,
                'None': None,
                'str': str,
                'globals': locals,
                'locals': locals,
                'bool': bool,
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'map': map,
                'abs': abs,
                'min': min,
                'max': max,
                'reduce': reduce,
                'filter': filter,
                'round': round,
                'len': len,
                'set' : set,
                #new
                'float': float,
                'int': int,
                'monthdelta': monthdelta,
            }
    )
    c = test_expr(expr, _SAFE_OPCODES, mode=mode)
    try:
        return eval(c, globals_dict, locals_dict)
    except openerp.osv.orm.except_orm:
        raise
    except openerp.exceptions.Warning:
        raise
    except openerp.exceptions.RedirectWarning:
        raise
    except openerp.exceptions.AccessDenied:
        raise
    except openerp.exceptions.AccessError:
        raise
    except Exception, e:
        import sys
        exc_info = sys.exc_info()
        raise ValueError, '"%s" while evaluating\n%r' % (str(e), expr), exc_info[2]

sys.modules['openerp.tools.safe_eval'].safe_eval = safe_eval_expand

def monthdelta(d1, d2):
    delta = 0
    d1=datetime.strptime(d1,"%Y-%m-%d")
    d2=datetime.strptime(d2,"%Y-%m-%d")
    while True:
        mdays = monthrange(d1.year, d1.month)[1]
        d1 += timedelta(days=mdays)
        if d1 <= d2:
            delta += 1
        else:
            break
    return delta
