import pandas as pd
from run_archive_corrections import e3_order_counts


def test_predicted_tie_is_neither_reversal_nor_match():
    df=pd.DataFrame({'pred':['A<B','A<B','tie','tie','A<B'],
                     'obs':['A<B','B<A','A<B','tie','tie']})
    result=e3_order_counts(df,'pred','obs')
    assert result=={'match':1,'ties':2,'reversal':1,'prediction_only_ties':1}
    assert sum(result.values())==len(df)


def test_strict_reverse_and_match_are_kept_when_predictions_are_not_tied():
    df=pd.DataFrame({'pred':['A<B','A<B','A<B'],'obs':['A<B','B<A','tie']})
    assert e3_order_counts(df,'pred','obs')=={
        'match':1,'ties':1,'reversal':1,'prediction_only_ties':0}


def test_empty_comparison_counts_are_zero():
    df=pd.DataFrame(columns=['pred','obs'])
    assert e3_order_counts(df,'pred','obs')=={
        'match':0,'ties':0,'reversal':0,'prediction_only_ties':0}
