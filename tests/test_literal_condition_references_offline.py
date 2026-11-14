"""Literal requirements: numbered conditions and later references to them.

A digit-bearing term in a definition becomes a literal requirement that an
item's own text must contain. A complete numbered list is recognised, so its
labels are not requirements. These cases fix two further rules:

- a quoted example inside a list item, closed just before a comma or the
  closing bracket, does not break the recognition of the list;
- one narrow kind of later sentence ("It must satisfy condition (2).") refers
  to a list label and is not a numeric fact. Anything else stays literal.

The cases come from the review of the scanner correction of 13 November 2026.
They use authored text only. No model, app or network is used.
"""
import unittest

from feedctrl import source_constraints


def terms(text, objective=''):
    return source_constraints.literal_requirements(objective, text)['terms']


class QuotedExamplesInsideAList(unittest.TestCase):
    def test_quoted_examples_with_immediate_comma_or_bracket(self):
        for left, right in [("'", "'"), ('‘', '’')]:
            text = (f"All three of: (1) an item has a fault (examples {left}bent{right}, {left}torn{right}); "
                    f"(2) a repair is done (such as {left}mended{right}); and (3) that object is kept. "
                    "A stated purpose or capability after the fix does not by itself satisfy condition (3).")
            with self.subTest(quote=left):
                self.assertEqual(terms(text), [])

    def test_ambiguous_possessive_or_unmatched_quotes_fail_closed(self):
        for text in ["All two of: (1) the owners' item exists; (2) the item is kept.",
                     "All two of: (1) the text is 'ready'; (2) the item is kept.",
                     "All two of: (1) an item (called 'ready) exists; (2) it is kept."]:
            with self.subTest(text=text):
                self.assertEqual(terms(text), ['1', '2'])

    def test_nested_or_quoted_lists_are_not_promoted(self):
        inner = 'all two of: (1) an item exists; (2) it is kept'
        for text in ['(' + inner + ')', '"' + inner + '"', "('" + inner + "')"]:
            with self.subTest(text=text):
                self.assertEqual(terms(text), ['1', '2'])


class ReferencesToAListLabel(unittest.TestCase):
    BASE = 'All two of: (1) an item exists; and (2) that item is kept.'
    PLAIN = 'All two of: (1) an item exists; (2) it is kept.'

    def test_actual_numeric_facts_and_references_are_distinct(self):
        text = ("All three of: (1) an item is rated (label 'IP68', score '90'); (2) a repair uses 1.5 litres; "
                "and (3) that object is retained for 3 years. A purpose does not satisfy condition (3).")
        self.assertEqual(terms(text), ['1.5', '3', '90', 'ip68'])
        self.assertEqual(terms(text, 'Exactly 1 item and 2 uses.'), ['1', '1.5', '2', '3', '90', 'ip68'])

    def test_only_unique_in_range_later_reference_is_masked(self):
        base = self.BASE
        self.assertEqual(terms(base + ' It must satisfy condition (2).'), [])
        self.assertEqual(terms(base + ' It satisfies condition (1).'), [])
        self.assertEqual(terms(base + ' A capability does not by itself satisfy condition (2).'), ['2'])
        for suffix, expected in [(' It must satisfy condition (3).', ['3']),
                                 (' It must satisfy condition (02).', ['02']),
                                 (' It must satisfy condition (2.0).', ['2.0']),
                                 (' The target is condition (2).', ['2']),
                                 (' It must satisfy condition (0).', ['0'])]:
            with self.subTest(suffix=suffix):
                self.assertEqual(terms(base + suffix), expected)
        self.assertEqual(terms('Satisfy condition (1). ' + base), ['1'])
        huge = '9' * 5000
        self.assertEqual(terms(base + ' It must satisfy condition (' + huge + ').'), [huge])

    def test_ambiguous_multiple_or_cross_input_lists_remain_literal(self):
        first = self.PLAIN
        second = ' All two of: (1) a plan exists; (2) it is active.'
        self.assertEqual(terms(first + second + ' It must satisfy condition (2).'), ['2'])
        self.assertEqual(terms(first + ' All two of: (1) a plan exists; (3) it is active. '
                                       'It must satisfy condition (2).'), ['1', '2', '3'])
        self.assertEqual(terms('It must satisfy condition (2).', first), ['2'])

    def test_quoted_or_nested_reference_is_not_masked(self):
        for suffix in [' The text says "satisfy condition (2)".', ' (It must satisfy condition (2).)',
                       ' [It must satisfy condition (2).]']:
            with self.subTest(suffix=suffix):
                self.assertEqual(terms(self.PLAIN + suffix), ['2'])

    def test_unquoted_mention_does_not_become_reference(self):
        base = self.PLAIN
        for suffix in [' The text must mention satisfy condition (2).',
                       ' The literal phrase is satisfy condition (2).',
                       ' The required text is condition (2).',
                       ' The text must mention it satisfies condition (2).',
                       ' The exact phrase must satisfy condition (2) literally.',
                       ' It must satisfy condition (2) as text.',
                       ' It must satisfy condition (2). This is a literal phrase.']:
            with self.subTest(suffix=suffix):
                self.assertEqual(terms(base + suffix), ['2'])
        self.assertEqual(terms(base + ' The text must mention version 5.4 then it satisfies condition (2).'),
                         ['2', '5.4'])
        self.assertEqual(terms(base + ' Please include e.g. it satisfies condition (2).'), ['2'])
        for suffix in [' The required inscription reads: it must satisfy condition (2).',
                       ' The label should show: it must satisfy condition (2).',
                       ' The display reads: It satisfies condition (2).',
                       ' It must satisfy condition (2) verbatim.']:
            with self.subTest(suffix=suffix):
                self.assertEqual(terms(base + suffix), ['2'])


if __name__ == '__main__':
    unittest.main()
