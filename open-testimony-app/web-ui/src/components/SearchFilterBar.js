import React, { useState, useEffect, useRef } from 'react';
import { Search, X, ChevronDown, ChevronUp } from 'lucide-react';

const CATEGORIES = ['interview', 'incident', 'documentation', 'other'];

export default function SearchFilterBar({
  filters,
  onFiltersChange,
  tagCounts,
  categoryCounts,
  totalCount,
  filteredCount,
}) {
  const [searchInput, setSearchInput] = useState(filters.search || '');
  const [showAllTags, setShowAllTags] = useState(false);
  const debounceRef = useRef(null);

  // Debounce search input
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (searchInput !== (filters.search || '')) {
        onFiltersChange({ ...filters, search: searchInput || '' });
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeCount =
    (filters.search ? 1 : 0) +
    (filters.tags.length) +
    (filters.category ? 1 : 0) +
    (filters.mediaType ? 1 : 0) +
    (filters.source ? 1 : 0);

  const clearAll = () => {
    setSearchInput('');
    onFiltersChange({ search: '', tags: [], category: '', mediaType: '', source: '' });
  };

  const toggleTag = (tag) => {
    const tags = filters.tags.includes(tag)
      ? filters.tags.filter(t => t !== tag)
      : [...filters.tags, tag];
    onFiltersChange({ ...filters, tags });
  };

  const setCategory = (cat) => {
    onFiltersChange({ ...filters, category: filters.category === cat ? '' : cat });
  };

  // Category counts lookup
  const catCountMap = {};
  (categoryCounts || []).forEach(c => { catCountMap[c.category] = c.count; });

  const visibleTags = showAllTags ? tagCounts : (tagCounts || []).slice(0, 8);
  const hiddenCount = (tagCounts || []).length - 8;

  return (
    <div className="border-b border-gray-700 bg-gray-800">
      {/* Search input */}
      <div className="p-3 pb-2">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            placeholder="Search notes, location, device..."
            className="w-full pl-9 pr-8 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          {searchInput && (
            <button
              onClick={() => { setSearchInput(''); onFiltersChange({ ...filters, search: '' }); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Category pills */}
      <div className="px-3 pb-2">
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => onFiltersChange({ ...filters, category: '' })}
            className={`shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium border transition ${
              !filters.category
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'bg-gray-900 border-gray-600 text-gray-400 hover:border-gray-500'
            }`}
          >
            All
          </button>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium border transition capitalize ${
                filters.category === cat
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-gray-900 border-gray-600 text-gray-400 hover:border-gray-500'
              }`}
            >
              {cat}{catCountMap[cat] ? ` (${catCountMap[cat]})` : ''}
            </button>
          ))}
        </div>
      </div>

      {/* Tag pills */}
      {tagCounts && tagCounts.length > 0 && (
        <div className="px-3 pb-2">
          <div className="flex flex-wrap gap-1.5">
            {visibleTags.map(t => (
              <button
                key={t.tag}
                onClick={() => toggleTag(t.tag)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium border transition uppercase tracking-tight ${
                  filters.tags.includes(t.tag)
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-900 border-gray-600 text-gray-400 hover:border-gray-500'
                }`}
              >
                {t.tag} ({t.count})
              </button>
            ))}
            {hiddenCount > 0 && (
              <button
                onClick={() => setShowAllTags(!showAllTags)}
                className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-gray-600 text-gray-500 hover:text-gray-300 hover:border-gray-500 transition flex items-center gap-0.5"
              >
                {showAllTags ? (
                  <>Less <ChevronUp size={10} /></>
                ) : (
                  <>+{hiddenCount} more <ChevronDown size={10} /></>
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Active filter chips with X to remove */}
      {activeCount > 0 && (
        <div className="px-3 pb-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {filters.tags.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full text-[10px] font-medium bg-blue-600 border border-blue-500 text-white uppercase tracking-tight"
              >
                {tag}
                <button
                  onClick={() => onFiltersChange({ ...filters, tags: filters.tags.filter(t => t !== tag) })}
                  className="rounded-full p-0.5 hover:bg-blue-500 transition"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
            {filters.category && (
              <span className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full text-[10px] font-medium bg-indigo-600 border border-indigo-500 text-white capitalize">
                {filters.category}
                <button
                  onClick={() => onFiltersChange({ ...filters, category: '' })}
                  className="rounded-full p-0.5 hover:bg-indigo-500 transition"
                >
                  <X size={10} />
                </button>
              </span>
            )}
            <button
              onClick={clearAll}
              className="text-[10px] text-blue-400 hover:text-blue-300 font-medium ml-1"
            >
              Clear all
            </button>
          </div>
        </div>
      )}

      {/* Result count */}
      <div className="px-3 pb-2">
        <span className="text-[11px] text-gray-500">
          Showing {filteredCount} of {totalCount}
        </span>
      </div>
    </div>
  );
}
