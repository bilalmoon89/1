"""Separate broad observation from the existing three-plan execution focus."""
from copy import deepcopy

FOLLOW_LIMIT=12
FOCUS_LIMIT=3


def follow_plan(following,plan):
    item=plan.to_dict() if hasattr(plan,'to_dict') else plan
    if item['id'] not in following and len(following)>=FOLLOW_LIMIT:
        raise ValueError('Watchtower is full. Remove an older setup first.')
    following.setdefault(item['id'],deepcopy(item))


def focus_plan(frozen,plan):
    item=plan.to_dict() if hasattr(plan,'to_dict') else plan
    if item['id'] not in frozen and len(frozen)>=FOCUS_LIMIT:
        raise ValueError('Three focus slots are already occupied.')
    frozen.setdefault(item['id'],deepcopy(item))
