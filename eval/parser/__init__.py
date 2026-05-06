"""Parser eval harness (T124).

Computes field-level accuracy of the Documentation Parser against the
synthetic dev split. AC-003-2 requires >= 0.90 field-level accuracy where a
field is considered "correct" when its predicted character offsets cover
80 to 120 percent of the ground-truth span.

Ground-truth spans for the synthetic encounter corpus are not currently
emitted by the generator (the generator records ground-truth verdicts, not
parser-stage section offsets). When ground-truth section offsets land in a
v1.1 generator extension, this harness will lift directly off them. Until
then, the harness operates on a small hand-labeled subset bundled in
``data/parser_eval/dev.jsonl``; that file is created lazily by anyone
running the harness for the first time.
"""

from eval.parser.field_accuracy import (
    FieldAccuracyReport,
    evaluate_field_accuracy,
)

__all__ = ["FieldAccuracyReport", "evaluate_field_accuracy"]
