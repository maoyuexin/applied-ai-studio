(function (root) {
  'use strict';
  function recommendationScores(data, history) {
    const scores = new Float64Array(data.catalog.length);
    for (const source of new Set(history)) {
      for (const [target, weight] of data.edges[source]) scores[target] += weight;
    }
    return scores;
  }
  function rank(data, history, blocked = []) {
    const seen = new Set(history), excluded = new Set([...history, ...blocked]);
    const scores = recommendationScores(data, history);
    const order = [...scores.keys()].filter(index => !excluded.has(index));
    const personalized = seen.size >= data.minHistory;
    order.sort((left, right) => scores[right] - scores[left] || left - right);
    const selected = personalized ? order.filter(index => scores[index] > 0).slice(0, data.slots) : [];
    const result = selected.map(index => ({index, score: scores[index], source: 'personalized'}));
    const fallback = [...data.fallback, ...[...scores.keys()].sort((left, right) => data.catalog[right][2] - data.catalog[left][2] || left - right)];
    const used = new Set([...excluded, ...selected]);
    for (const index of fallback) {
      if (result.length >= data.slots) break;
      if (!used.has(index)) {
        result.push({index, score: null, source: 'fallback'});
        used.add(index);
      }
    }
    return {result, personalized, scores};
  }
  function contributions(data, history, target) {
    return [...new Set(history)].map(source => ({source,
      weight: (data.edges[source].find(edge => edge[0] === target) || [target, 0])[1]
    })).filter(record => record.weight > 0).sort((left, right) => right.weight - left.weight || left.source - right.source);
  }
  function predict(data, features) {
    let result = data.bias;
    for (const tree of data.trees) {
      let index = 0;
      while (!tree[index][5]) {
        const node = tree[index], value = features[node[0]];
        const left = value === null || !Number.isFinite(value) ? !!node[4] : value <= node[1];
        index = left ? node[2] : node[3];
      }
      result += tree[index][6];
    }
    return Math.max(0, result);
  }
  function featureRow(units, target, weekNumber, recent = null) {
    const history = units.slice(0, target);
    if (recent) history.splice(target - 8, 8, ...recent);
    const mean = count => history.slice(-count).reduce((total, value) => total + value, 0) / count;
    const mean4 = mean(4), mean8 = mean(8);
    const deviation = Math.sqrt(history.slice(-4).reduce((total, value) => total + (value - mean4) ** 2, 0) / 4);
    return [1, 2, 3, 4, 8].map(lag => history[target - lag]).concat([
      mean4, mean8, deviation, target >= 52 ? history[target - 52] : null,
      Math.sin(2 * Math.PI * weekNumber / 52), Math.cos(2 * Math.PI * weekNumber / 52), weekNumber
    ]);
  }
  function explain(data, features) {
    const values = [];
    for (let mask = 0; mask < 16; mask++) {
      let total = 0;
      for (const reference of data.background) {
        const mixed = reference.slice();
        data.groups.forEach((group, index) => {
          if (mask & (1 << index)) for (const feature of group) mixed[feature] = features[feature];
        });
        total += predict(data, mixed);
      }
      values[mask] = total / data.background.length;
    }
    const weights = [1 / 4, 1 / 12, 1 / 12, 1 / 4];
    const effects = data.groups.map((_, group) => {
      let effect = 0;
      for (let mask = 0; mask < 16; mask++) {
        if (mask & (1 << group)) continue;
        const size = mask.toString(2).replaceAll('0', '').length;
        effect += weights[size] * (values[mask | (1 << group)] - values[mask]);
      }
      return effect;
    });
    return {reference: values[0], effects, prediction: predict(data, features)};
  }
  root.RetailEngine = {recommendationScores, rank, contributions, predict, featureRow, explain};
  if (typeof module !== 'undefined') module.exports = root.RetailEngine;
})(globalThis);