-- The flows exist as columns on fct_half_hour and as rows here. If the two ever
-- disagree, one of them has been changed without the other. The null branch matters:
-- abs(x - null) is null, so a blanked wide total would otherwise pass silently.
select f.start_time,
       round(sum(f.flow_mw), 2) as long_total,
       round(max(h.interconnector_net_mw), 2) as wide_total
from {{ ref('fct_interconnector_flow') }} f
join {{ ref('fct_half_hour') }} h using (start_time)
where f.is_cross_border
group by f.start_time
having max(h.interconnector_net_mw) is null
    or abs(sum(f.flow_mw) - max(h.interconnector_net_mw)) > 0.01
