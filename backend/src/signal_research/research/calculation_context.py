"""Readable references to existing arithmetic, preserving ordered input lineage."""


def calculation_context(calculation, facts):
    by_id = {fact.id: fact for fact in facts}
    inputs = [by_id[identifier] for identifier in calculation.input_fact_ids]
    formula = calculation.formula_id
    segment_roles = (['selected_revenue_component', *['other_revenue_component']*(len(inputs)//2-2), 'reported_segment_revenue_total',
                      'selected_result_component', *['other_result_component']*(len(inputs)//2-2), 'reported_segment_result_total']
                     if formula == 'segment_dependency_gap' else
                     ['selected_component', *['other_component']*(len(inputs)-2), 'reported_segment_total'])
    roles = (['current', 'post_break_trough', 'pre_break'] if formula == 'recovery_ratio' else
             segment_roles if formula.startswith('segment_') else
             ['current_deposits', 'current_borrowings', 'trough_deposits', 'trough_borrowings', 'pre_break_deposits', 'pre_break_borrowings'] if formula == 'recovery_ratio_funding_mix' else
             ['first_current', 'first_prior', 'second_current', 'second_prior']
             if formula in {'growth_gap', 'ldr_change'} else
             ['deposits_current', 'borrowings_current', 'deposits_prior', 'borrowings_prior']
             if formula == 'deposit_borrowing_mix_change' else
             ['start', 'end'] if formula == 'cagr' else
             ['current', 'prior'] if formula in {'yoy_growth', 'change_pp', 'change_bps'} else
             ['numerator', 'denominator'])
    result = calculation.model_dump(mode='json')
    result['input_bindings'] = [
        {'id': fact.id, 'role': roles[index], 'metric': fact.metric_key,
         'value': fact.value_decimal, 'period_start': fact.period_start,
         'period_end': fact.period_end, 'scope': fact.scope, 'segment': fact.segment,
         'definition_id': fact.definition_id}
        for index, fact in enumerate(inputs)]
    # Decimal formatting provides a copyable value without changing the saved
    # exact result or the independent reproduction used by publication checks.
    result['output_display'] = (f'{calculation.output_value:.{calculation.precision}f}'
                                if calculation.output_value is not None else None)
    if formula == 'growth_gap':
        result['reading'] = (f'YoY growth in {inputs[0].metric_key} minus YoY growth in '
            f'{inputs[2].metric_key}; a negative value means the first metric grew more slowly. '
            'This is one comparable growth interval, not a change in the gap between intervals.')
    elif formula == 'yoy_growth':
        result['reading'] = f'YoY percentage change in {inputs[0].metric_key}; negative means decline.'
    elif formula in {'change_pp', 'change_bps'}:
        result['reading'] = f'Current minus prior {inputs[0].metric_key}; negative means decline.'
    elif formula.startswith('deposit_borrowing_mix'):
        result['reading'] = ('Deposits as a share of deposits plus borrowings; excludes capital and other liabilities. '
                             + ('Current share minus prior share in percentage points.' if formula.endswith('_change') else 'Not a share of all funding.'))
    elif formula.startswith('segment_'):
        result['reading'] = ('Components reconcile exactly to their separately disclosed segment total. Gross segment revenue may include intersegment activity; segment results are not consolidated net profit. '
                             + ('Result contribution minus revenue contribution for the same named segment; this is a single reporting window, not a growth trend.' if formula.endswith('_gap') else 'A contribution within the reported segment schedule.'))
    return result
