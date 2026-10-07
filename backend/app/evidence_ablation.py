"""A fixed, oracle-independent transform that never copies raw trace text."""
import builtins
import re

VERSION = 'exception-type-evidence-1.0.0'
MODES = ('fresh_regression_output', 'exception_type_only')
BUILTIN_TYPES = {name for name, value in vars(builtins).items() if isinstance(value, type) and issubclass(value, Exception)}
EXCEPTION_LINE = re.compile(r'^(?:E\s+)?([A-Za-z_][A-Za-z0-9_.]*)(?::|\s*$)', re.M)
NOTE = 'Only recognized built-in exception types are retained. Messages, frames, file paths, line numbers, test names, and source excerpts are omitted. Unknown does not mean no failure.'


def transform(evidence, mode):
    if mode not in MODES:
        raise ValueError('Unsupported real evidence mode')
    output = evidence.get('fresh_failing_test_output')
    if not isinstance(output, str) or not output.strip():
        raise ValueError('Frozen failing-test output missing')
    if mode == 'fresh_regression_output':
        return {'fresh_failing_test_output': output}
    types = sorted({match.group(1) for match in EXCEPTION_LINE.finditer(output) if match.group(1) in BUILTIN_TYPES})
    return {'exception_types': types, 'extraction_status': 'recognized_builtin_type' if types else 'unknown',
            'note': NOTE}
