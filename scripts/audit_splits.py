import json
from collections import defaultdict

data = json.load(open('backend/data/test_queries.json', encoding='utf-8'))
cat_counts = defaultdict(lambda: {'dev': 0, 'test': 0})
type_counts = defaultdict(lambda: {'dev': 0, 'test': 0})

for q in data:
    cat_counts[q['category']][q['split']] += 1
    type_counts[q['benchmark_type']][q['split']] += 1

print(f"{'Category':<22} | {'Dev':<5} | {'Test':<5} | {'Total':<5} | {'Dev %':<6}")
print("-" * 52)
for cat, counts in sorted(cat_counts.items()):
    tot = counts['dev'] + counts['test']
    pct = counts['dev'] / tot * 100 if tot else 0
    print(f"{cat:<22} | {counts['dev']:>5} | {counts['test']:>5} | {tot:>5} | {pct:>5.1f}%")

print("\n" + f"{'Benchmark Type':<22} | {'Dev':<5} | {'Test':<5} | {'Total':<5} | {'Dev %':<6}")
print("-" * 52)
for btype, counts in sorted(type_counts.items()):
    tot = counts['dev'] + counts['test']
    pct = counts['dev'] / tot * 100 if tot else 0
    print(f"{btype:<22} | {counts['dev']:>5} | {counts['test']:>5} | {tot:>5} | {pct:>5.1f}%")

frozen_dev = [q['id'] for q in data[:25] if q['split'] == 'dev']
frozen_test = [q['id'] for q in data[:25] if q['split'] == 'test']
print(f"\nFrozen Q001-Q025 in dev ({len(frozen_dev)}): {frozen_dev}")
print(f"Frozen Q001-Q025 in test ({len(frozen_test)}): {frozen_test}")
