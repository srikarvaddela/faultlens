"""Original educational fixtures. No third-party benchmark claims."""

CATALOG = [
    {
        "id": "FL-001", "title": "Discount applied at the wrong scale",
        "module": "checkout/pricing.py", "category": "Arithmetic", "difficulty": "Easy",
        "description": "Large orders cost less than zero when a percentage discount is applied. Small orders still pass.",
        "function": "total", "fault_line": 3,
        "source": "def total(subtotal, percent):\n    if subtotal >= 100:\n        return subtotal * (1 - percent)\n    return subtotal\n",
        "fixed_source": "def total(subtotal, percent):\n    if subtotal >= 100:\n        return subtotal * (1 - percent / 100)\n    return subtotal\n",
        "fix_explanation": "Convert the percentage to a fraction before multiplying the subtotal.",
        "tests": [
            {"name": "small_order", "args": [50, 20], "expected": 50},
            {"name": "below_threshold", "args": [99, 10], "expected": 99},
            {"name": "threshold_order", "args": [100, 20], "expected": 80},
            {"name": "large_order", "args": [200, 10], "expected": 180},
            {"name": "zero_discount", "args": [150, 0], "expected": 150},
        ],
    },
    {
        "id": "FL-002", "title": "Even-length median shifts one position",
        "module": "stats/median.py", "category": "Indexing", "difficulty": "Medium",
        "description": "Odd-length samples work, but even-length samples use the wrong pair of middle elements.",
        "function": "median", "fault_line": 6,
        "source": "def median(values):\n    ordered = sorted(values)\n    middle = len(ordered) // 2\n    if len(ordered) % 2:\n        return ordered[middle]\n    return (ordered[middle] + ordered[middle + 1]) / 2\n",
        "fixed_source": "def median(values):\n    ordered = sorted(values)\n    middle = len(ordered) // 2\n    if len(ordered) % 2:\n        return ordered[middle]\n    return (ordered[middle - 1] + ordered[middle]) / 2\n",
        "fix_explanation": "The central pair is at middle - 1 and middle for an even-length sample.",
        "tests": [
            {"name": "single_value", "args": [[7]], "expected": 7},
            {"name": "odd_sorted", "args": [[1, 3, 9]], "expected": 3},
            {"name": "odd_unsorted", "args": [[9, 1, 3]], "expected": 3},
            {"name": "two_values", "args": [[2, 8]], "expected": 5},
            {"name": "four_values", "args": [[1, 2, 3, 4]], "expected": 2.5},
        ],
    },
    {
        "id": "FL-003", "title": "Pagination drops the last item",
        "module": "api/pagination.py", "category": "Boundary", "difficulty": "Easy",
        "description": "Each page is one item shorter than requested because Python slice endpoints are exclusive.",
        "function": "paginate", "fault_line": 3,
        "source": "def paginate(items, page, size):\n    start = (page - 1) * size\n    return items[start:start + size - 1]\n",
        "fixed_source": "def paginate(items, page, size):\n    start = (page - 1) * size\n    return items[start:start + size]\n",
        "fix_explanation": "An exclusive endpoint of start + size returns exactly size elements.",
        "tests": [
            {"name": "empty_page", "args": [[], 1, 3], "expected": []},
            {"name": "past_end", "args": [[1, 2], 3, 2], "expected": []},
            {"name": "first_page", "args": [[1, 2, 3, 4, 5, 6], 1, 3], "expected": [1, 2, 3]},
            {"name": "second_page", "args": [[1, 2, 3, 4, 5, 6], 2, 3], "expected": [4, 5, 6]},
            {"name": "single_item_page", "args": [[1, 2], 1, 1], "expected": [1]},
        ],
    },
    {
        "id": "FL-004", "title": "Clamp always collapses to the lower bound",
        "module": "utils/bounds.py", "category": "Logic", "difficulty": "Easy",
        "description": "Values below the lower bound look correct, masking the incorrect bound inside min().",
        "function": "clamp", "fault_line": 2,
        "source": "def clamp(value, lower, upper):\n    return max(lower, min(value, lower))\n",
        "fixed_source": "def clamp(value, lower, upper):\n    return max(lower, min(value, upper))\n",
        "fix_explanation": "The inner min() must enforce the upper bound; the outer max() enforces the lower bound.",
        "tests": [
            {"name": "below_range", "args": [-2, 0, 10], "expected": 0},
            {"name": "lower_boundary", "args": [0, 0, 10], "expected": 0},
            {"name": "inside_range", "args": [5, 0, 10], "expected": 5},
            {"name": "above_range", "args": [12, 0, 10], "expected": 10},
            {"name": "negative_range", "args": [-5, -10, -1], "expected": -5},
        ],
    },
    {
        "id": "FL-005", "title": "Slug keeps repeated whitespace",
        "module": "content/slug.py", "category": "Text processing", "difficulty": "Easy",
        "description": "Replacing individual spaces creates duplicate separators and leaves tabs in generated URLs.",
        "function": "slugify", "fault_line": 4,
        "source": "def slugify(title):\n    if not title.strip():\n        return ''\n    return title.strip().lower().replace(' ', '-')\n",
        "fixed_source": "def slugify(title):\n    if not title.strip():\n        return ''\n    return '-'.join(title.lower().split())\n",
        "fix_explanation": "Split on whitespace and join tokens to normalize spaces and tabs consistently.",
        "tests": [
            {"name": "empty_title", "args": [""], "expected": ""},
            {"name": "whitespace_only", "args": ["   "], "expected": ""},
            {"name": "simple_title", "args": ["Hello World"], "expected": "hello-world"},
            {"name": "repeated_spaces", "args": ["Hello   World"], "expected": "hello-world"},
            {"name": "tab_separator", "args": ["Hello\tWorld"], "expected": "hello-world"},
        ],
    },
    {
        "id": "FL-006", "title": "Moving average omits the final window",
        "module": "stats/windows.py", "category": "Boundary", "difficulty": "Medium",
        "description": "A full-size window returns no output, and longer series lose their final rolling average.",
        "function": "moving_average", "fault_line": 4,
        "source": "def moving_average(values, window):\n    if window <= 0:\n        raise ValueError('window must be positive')\n    return [sum(values[i:i + window]) / window for i in range(len(values) - window)]\n",
        "fixed_source": "def moving_average(values, window):\n    if window <= 0:\n        raise ValueError('window must be positive')\n    return [sum(values[i:i + window]) / window for i in range(len(values) - window + 1)]\n",
        "fix_explanation": "There are n - window + 1 complete windows, including the last valid starting index.",
        "tests": [
            {"name": "empty_series", "args": [[], 2], "expected": []},
            {"name": "too_short", "args": [[1], 2], "expected": []},
            {"name": "full_size_window", "args": [[2, 4], 2], "expected": [3]},
            {"name": "rolling_pair", "args": [[1, 2, 3, 4], 2], "expected": [1.5, 2.5, 3.5]},
            {"name": "unit_window", "args": [[1, 2], 1], "expected": [1, 2]},
        ],
    },
]

BY_ID = {bug["id"]: bug for bug in CATALOG}


def public_bug(bug):
    return {key: value for key, value in bug.items() if key != "fixed_source"}
