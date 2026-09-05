export type ResearchPaper = {
  id: string
  title: string
  authors: string[]
  publication_year: number | null
  abstract: string | null
  doi: string | null
  url: string | null
  publication_date?: string | null
  citation_count?: number | null
  source_name?: string | null
}

export type ResearchSearchResponse = {
  query: string
  total: number
  results: ResearchPaper[]
  page: number
  limit: number
  sort: SortOption
}

export type SortOption = 'relevance' | 'cited' | 'newest' | 'oldest'

export type SearchFilters = {
  from_year?: number
  to_year?: number
  open_access: boolean
  has_doi: boolean
}

export type SavedPaper = Omit<ResearchPaper, 'id'> & {
  id: number
  openalex_id: string
  created_at: string
  updated_at: string
}

export type SavedPapersResponse = {
  items: SavedPaper[]
  page: number
  limit: number
  total: number
  pages: number
}
