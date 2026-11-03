import pytest
from watchtower import follow_plan, focus_plan


def plan(i):
    return {'id':str(i),'symbol':'TEST','trigger':100,'stop':98,'status':'WATCH'}


def test_twelve_followed_setups_do_not_expand_three_focus_slots():
    following={};frozen={}
    for i in range(12):follow_plan(following,plan(i))
    assert len(following)==12
    assert not frozen
    with pytest.raises(ValueError):follow_plan(following,plan(12))
    for i in range(3):focus_plan(frozen,following[str(i)])
    with pytest.raises(ValueError):focus_plan(frozen,following['3'])
    assert len(frozen)==3


def test_followed_levels_are_not_rewritten_by_next_scan():
    following={};item=plan(0)
    follow_plan(following,item)
    item['trigger']=101
    follow_plan(following,item)
    assert following['0']['trigger']==100
