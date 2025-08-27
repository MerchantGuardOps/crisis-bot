from typing import List, Dict

def get_application_order(intake: Dict) -> List[str]:
    """Determine application order based on business model and MATCH status"""
    biz = (intake.get('commerce', {}).get('business_model') or '').lower()
    is_match = bool(intake.get('processing', {}).get('match_listed'))

    if biz == 'saas' and not is_match:
        return ['fastspring', 'paddle', 'paymentcloud', 'durango', 'emb']
    if is_match:
        return ['durango','paymentcloud','fastspring','emb','soar'] if biz == 'saas' \
               else ['durango','paymentcloud','emb','soar','host']
    if biz == 'physical_goods':
        return ['paymentcloud','durango','emb','soar','host']
    return ['fastspring','paymentcloud','durango','emb','soar']

def rank_with_runtime_signals(base_order: List[str], runtime_stats: Dict[str, Dict]) -> List[str]:
    """Reorder providers based on observed success rates and timeframes"""
    if not runtime_stats:
        return base_order
    
    days = [v.get('days') for v in runtime_stats.values() if v.get('days')]
    dmin, dmax = (min(days), max(days)) if days else (None, None)

    def score(pid: str):
        s = runtime_stats.get(pid, {})
        succ, d = s.get('success'), s.get('days')
        if succ is None: 
            return -1
        t = 0.0
        if d and dmin is not None and dmax != dmin:
            t = 1 - (d - dmin) / (dmax - dmin)
        return 0.7*succ + 0.3*t

    return sorted(base_order, key=lambda pid: (score(pid), -base_order.index(pid)), reverse=True)