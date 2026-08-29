"""Evaluation assets for the Assistant Agent.

Kept apart from the translation harness at the top of `eval/` because the two
measure different things over different data, and mixing them would make
`golden_set.jsonl` ambiguous about which agent a row belongs to.
"""
