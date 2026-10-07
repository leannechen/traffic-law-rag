import { item } from '../../test-utils'
import { articleIdOf, groupArticles, sortForDone } from './articles'

describe('articleIdOf', () => {
  it('strips the split suffix only', () => {
    expect(articleIdOf('K0040012:35-p2')).toBe('K0040012:35')
    expect(articleIdOf('K0040012:35-1')).toBe('K0040012:35-1')
    expect(articleIdOf('K0040012:35-1-p10')).toBe('K0040012:35-1')
  })
})

describe('groupArticles', () => {
  it('merges chunks of one article and keeps the best score', () => {
    const grouped = groupArticles([
      item('K0040012:35-p1', 1, 0.6, '35'),
      item('K0040012:53', 2, 0.7, '53'),
      item('K0040012:35-p2', 3, 0.65, '35'),
    ])
    expect(grouped.map((g) => [g.articleId, g.score])).toEqual([
      ['K0040012:35', 0.65],
      ['K0040012:53', 0.7],
    ])
  })
})

describe('sortForDone', () => {
  it('puts cited articles first and keeps the order inside each group', () => {
    const grouped = groupArticles([
      item('A:1', 1, 0.9, '1'),
      item('A:2', 2, 0.8, '2'),
      item('A:3', 3, 0.7, '3'),
    ])
    expect(sortForDone(grouped, ['A:3', 'A:2']).map((g) => g.articleId)).toEqual([
      'A:2',
      'A:3',
      'A:1',
    ])
  })
})
