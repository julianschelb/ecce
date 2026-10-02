# ECCE — Entity-Centric Corpus Exploration

ECCE turns text corpora into **implicit entity networks** (Spitz & Gertz) and lets you explore
them in the browser: a page-by-page reader with highlighted mentions, an interactive entity graph
that doubles as a search tool, a book index,
full-text search cross-referenced with entities, and a password-protected admin panel for adding
and processing corpora. This is the modernised successor of the original Flask/Vue/MongoDB
prototype ([ECCE, WWW '22](https://doi.org/10.1145/3487553.3524237)).

```
.
├── backend/      FastAPI · SQLite (SQLModel, FTS5) · implicit-word-network engine
├── frontend/     React 19 · TypeScript · Vite · Tailwind CSS · force-graph canvas
├── Dockerfile    full-stack image (frontend built and served by the API) — used by Railway
├── docker-compose.yml   two-service local deployment (nginx + API)
└── railway.json
```

## Features

- **Public gallery** of precomputed, ready-to-explore corpora with metadata (genre, documents,
  chunks, entities, edges, date). Visitors cannot create collections.
- **Reader first**: every corpus is read page by page (about 300 words per page, chapters start
  on a new page) with entity mentions highlighted and animated page turns; the page and the
  selected entity live in the URL, ← / → turn pages, and neighbouring pages are prefetched.
  Hovering a mention shows its closest connections and switches the graph to its ego network.
- **Graph as a search tool**: the force-directed entity network (node size = strength, colour =
  entity type, ego networks, weight/count/type filters) sits next to the reader. Clicking an
  entity lists every page that mentions it, clicking a link lists the pages where both entities
  appear together, and "This page" restricts the network to the entities on the current page.
  A zoom slider sits in the graph corner; the initial view is zoomed so that the most mentioned
  entities are readable, and the panel can be hidden or given the full width.
- **Book index and contents**: a back-of-the-book index lists all mentioned entities with their
  page numbers (filter by name or type) and a table of contents maps chapters to page ranges.
- **Search**: SQLite FTS5 (BM25 ranking, snippets) over passages, optionally restricted to
  passages mentioning the selected entities; hits open the page with the terms marked.
- **Admin panel** (`/admin`, `ADMIN_PASSWORD`): paste text or upload `.txt`/`.md` files in batch,
  trigger background processing with live job progress, hide/show and delete corpora.
- **Graph engine**: the [`implicit-word-network`](https://pypi.org/project/implicit-word-network/)
  package computes ω(v, w) = Σ exp(−δ) with sparse matrix products; edges are single weighted
  cooccurrence edges (multi-context edge clustering of the prototype was dropped).
- **Swappable extractors**: spaCy (default when installed), zero-shot GLiNER, or a dependency-free
  rule-based fallback — all CPU-only.
- **Seed data**: 28 public-domain corpora ship precomputed (`backend/data/seed/*.json.gz`) and are
  imported on first start, so the app works immediately: *Alice's Adventures in Wonderland* plus 26
  further Project Gutenberg classics processed with spaCy, and Vergil's complete Latin works from
  the Perseus Digital Library processed with the LatinCy `la_core_web_md` pipeline (the Aeneid is
  the source corpus of the Loci Similes intertextuality benchmark).

## Quick start (local development)

```bash
# backend
cd backend
uv venv && uv pip install -e ".[dev,spacy]"        # or: pip install -e ".[dev,spacy]"
ADMIN_PASSWORD=change-me .venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (second terminal; proxies /api to :8000)
cd frontend
npm install && npm run dev                         # http://localhost:5173
```

API docs: http://localhost:8000/api/docs

## Tests and checks

```bash
cd backend && .venv/bin/pytest                     # graph, auth, search, admin, seed round-trip
cd frontend && npm run build                       # type-check + production bundle
```

## Docker

```bash
# two services (nginx frontend on :8080, API on :8000), persistent SQLite volume
ADMIN_PASSWORD=change-me docker compose up --build

# single full-stack image (what Railway runs)
docker build -t ecce . && docker run -p 8000:8000 -e ADMIN_PASSWORD=change-me ecce
```

## Deploying on Railway

The root `Dockerfile` + `railway.json` deploy ECCE as **one service**: the React build is served by
FastAPI, which also exposes the API under `/api`. Steps:

1. Create a project and connect a service to this GitHub repository (branch `main`); every push
   to `main` then builds and deploys the root `Dockerfile` (after CI passes).
2. Set variables: `ADMIN_PASSWORD` (required for the admin panel), optionally `SECRET_KEY`
   (stable tokens across restarts), `EXTRACTOR` (`auto` → spaCy), `CORS_ORIGINS`, `PUBLIC_URL`
   (the site's main address, used for canonical links and the sitemap).
3. Attach a **volume** mounted at `/app/data` so the SQLite database survives redeploys, and set
   `RAILWAY_RUN_UID=0` (Railway mounts volumes root-owned; the image otherwise runs as a non-root user).
4. Railway injects `PORT`; the image binds to it and reports health at `/api/health`.
5. For a public instance run from the EU: set `LEGAL_NAME`, `LEGAL_ADDRESS` and `LEGAL_EMAIL` for the
   legal notice and privacy policy, and sign Railway's
   [Data Processing Addendum](https://railway.com/legal/dpa), which the privacy policy relies on for
   hosting outside the EU. The app sets no cookies, loads nothing from third parties (fonts and the
   API docs UI are bundled) and shows the licence of every text.

The live instance runs at <https://ecce-production-af60.up.railway.app> (custom domain
`corpus-exploration.net` pending DNS).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_PASSWORD` | unset | Enables `/admin` and the write API |
| `SECRET_KEY` | random | Signs admin bearer tokens (HS256, 12 h) |
| `DATA_DIR` | `data` | SQLite database (mount a volume here) |
| `SEED_DIR` | `<DATA_DIR>/seed` | Precomputed `*.json` corpora imported when missing |
| `DATABASE_URL` | `sqlite:///<DATA_DIR>/ecce.db` | SQLAlchemy URL |
| `EXTRACTOR` | `auto` | `rule`, `spacy`, `gliner` |
| `WINDOW` | `2` | Cooccurrence window in sentences |
| `MAX_CHUNK_WORDS` | `180` | Paragraph chunk size |
| `FRONTEND_DIST` | unset | Serve a built SPA from this folder |
| `CORS_ORIGINS` | localhost dev ports | JSON list |
| `LEGAL_NAME`, `LEGAL_ADDRESS`, `LEGAL_EMAIL` | unset | Operator named in the legal notice (`/legal`, § 5 DDG) and privacy policy (`/privacy`); separate address lines with `\|` |
| `LOG_RETENTION_DAYS` | `7` | Access-log retention stated in the privacy policy (Railway Hobby: 7 days) |
| `CONTACT_RETENTION_DAYS` | `180` | Contact form messages are deleted after this many days |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | unset | Optional: e-mail each contact message to `LEGAL_EMAIL` |
| `PUBLIC_URL` | unset | Canonical origin (e.g. `https://www.corpus-exploration.net`): canonical links, `sitemap.xml`, and a 301 redirect from other hosts |
| `SEED_ON_STARTUP` | `true` | Import bundled corpora when missing |
| `SEED_ASYNC` | `false` | Import seeds on a background thread (set in the images) |

## API overview

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/corpora` | – | Gallery (visible + ready); `?all=1` for admins |
| GET | `/api/corpora/{slug}` | – | Metadata, entity-type counts, top entities |
| GET | `/api/corpora/{slug}/graph` | – | `min_weight`, `max_nodes`, `labels`, `focus` |
| GET | `/api/corpora/{slug}/entities` · `/entities/{id}` | – | Lookup, detail with neighbours |
| GET | `/api/corpora/{slug}/edges/{a}/{b}` | – | Edge weight/count and shared passages |
| GET | `/api/corpora/{slug}/pages/{n}` · `/pages/{n}/graph` | – | One reading page (passages, entities); its entity network |
| GET | `/api/corpora/{slug}/pages` | – | Pages mentioning `entity_id` (all of them) / in `document_id` |
| GET | `/api/corpora/{slug}/index` | – | Book index: every entity with its page numbers (`q`, `label`) |
| GET | `/api/corpora/{slug}/documents` · `/chunks` | – | Chapters with first pages; raw passage reader |
| GET | `/api/corpora/{slug}/search?q=` | – | Full-text search (FTS5, BM25, snippets, page numbers) |
| POST | `/api/auth/login` | – | Password → bearer token |
| POST | `/api/admin/corpora` · `/corpora/upload` | admin | Create from text / files |
| POST | `/api/admin/corpora/{slug}/process` | admin | Background processing job |
| PATCH/DELETE | `/api/admin/corpora/{slug}` | admin | Edit, hide, delete |
| GET | `/api/admin/jobs` · `/jobs/{id}` | admin | Job status |

## Bundled corpora

| Title | Author (died) | Year | Source |
|---|---|---|---|
| Flatland | Edwin A. Abbott (†1926) | 1884 | Project Gutenberg #97 |
| Little Women | Louisa May Alcott (†1888) | 1868 | Project Gutenberg #514 |
| The Divine Comedy | Dante Alighieri (†1321, †1844, †1883) | 1320 | Project Gutenberg #8800 |
| Winesburg, Ohio | Sherwood Anderson (†1941) | 1919 | Project Gutenberg #416 |
| The Enchanted April | Elizabeth von Arnim (†1941) | 1922 | Project Gutenberg #16389 |
| Sense and Sensibility | Jane Austen (†1817) | 1811 | Project Gutenberg #161 |
| Pride and Prejudice | Jane Austen (†1817) | 1813 | Project Gutenberg #1342 |
| Mansfield Park | Jane Austen (†1817) | 1814 | Project Gutenberg #141 |
| Emma | Jane Austen (†1817) | 1815 | Project Gutenberg #158 |
| Persuasion | Jane Austen (†1817) | 1817 | Project Gutenberg #105 |
| Northanger Abbey | Jane Austen (†1817) | 1817 | Project Gutenberg #121 |
| Eugénie Grandet | Honoré de Balzac (†1850, †1908) | 1833 | Project Gutenberg #1715 |
| Father Goriot | Honoré de Balzac (†1850, †1946) | 1835 | Project Gutenberg #1237 |
| Peter Pan | J. M. Barrie (†1937) | 1911 | Project Gutenberg #16 |
| The Wonderful Wizard of Oz | L. Frank Baum (†1919) | 1900 | Project Gutenberg #55 |
| The Marvelous Land of Oz | L. Frank Baum (†1919, †1943) | 1904 | Project Gutenberg #54 |
| Looking Backward, 2000 to 1887 | Edward Bellamy (†1898) | 1888 | Project Gutenberg #624 |
| Lorna Doone | R. D. Blackmore (†1900) | 1869 | Project Gutenberg #17460 |
| The Decameron | Giovanni Boccaccio (†1375, †1916) | 1353 | Project Gutenberg #23700 |
| Lady Audley's Secret | Mary Elizabeth Braddon (†1915) | 1862 | Project Gutenberg #8954 |
| Jane Eyre | Charlotte Brontë (†1855, †1920) | 1847 | Project Gutenberg #1260 |
| Wuthering Heights | Emily Brontë (†1848) | 1847 | Project Gutenberg #768 |
| Agnes Grey | Anne Brontë (†1849) | 1847 | Project Gutenberg #767 |
| The Tenant of Wildfell Hall | Anne Brontë (†1849, †1920) | 1848 | Project Gutenberg #969 |
| Shirley | Charlotte Brontë (†1855) | 1849 | Project Gutenberg #30486 |
| Villette | Charlotte Brontë (†1855) | 1853 | Project Gutenberg #9182 |
| The Thirty-Nine Steps | John Buchan (†1940) | 1915 | Project Gutenberg #558 |
| The Coming Race | Edward Bulwer-Lytton (†1873) | 1871 | Project Gutenberg #1951 |
| The Pilgrim's Progress | John Bunyan (†1688) | 1678 | Project Gutenberg #131 |
| Little Lord Fauntleroy | Frances Hodgson Burnett (†1924) | 1886 | Project Gutenberg #479 |
| A Little Princess | Frances Hodgson Burnett (†1924) | 1905 | Project Gutenberg #146 |
| The Secret Garden | Frances Hodgson Burnett (†1924) | 1911 | Project Gutenberg #17396 |
| Evelina | Fanny Burney (†1840) | 1778 | Project Gutenberg #6053 |
| Tarzan of the Apes | Edgar Rice Burroughs (†1950) | 1912 | Project Gutenberg #78 |
| A Princess of Mars | Edgar Rice Burroughs (†1950) | 1917 | Project Gutenberg #62 |
| The Land That Time Forgot | Edgar Rice Burroughs (†1950) | 1918 | Project Gutenberg #551 |
| The Gods of Mars | Edgar Rice Burroughs (†1950) | 1918 | Project Gutenberg #64 |
| The Way of All Flesh | Samuel Butler (†1902) | 1903 | Project Gutenberg #2084 |
| The Iliad | Homer (translated by Samuel Butler) (†-650, †1902) | c. 750 BCE | Project Gutenberg #2199 |
| The Odyssey | Homer (translated by Samuel Butler) (†-650, †1902) | c. 700 BCE | Project Gutenberg #1727 |
| Through the Looking-Glass | Lewis Carroll (†1898) | 1871 | Project Gutenberg #12 |
| O Pioneers! | Willa Cather (†1947) | 1913 | Project Gutenberg #24 |
| The Song of the Lark | Willa Cather (†1947) | 1915 | Project Gutenberg #44 |
| My Ántonia | Willa Cather (†1947) | 1918 | Project Gutenberg #242 |
| Don Quixote | Miguel de Cervantes (†1616, †1895) | 1605 | Project Gutenberg #996 |
| The King in Yellow | Robert W. Chambers (†1933) | 1895 | Project Gutenberg #8492 |
| The Napoleon of Notting Hill | G. K. Chesterton (†1936, †1948) | 1904 | Project Gutenberg #20058 |
| The Man Who Was Thursday | G. K. Chesterton (†1936) | 1908 | Project Gutenberg #1695 |
| The Innocence of Father Brown | G. K. Chesterton (†1936) | 1911 | Project Gutenberg #204 |
| The Riddle of the Sands | Erskine Childers (†1922) | 1903 | Project Gutenberg #2360 |
| The Awakening | Kate Chopin (†1904) | 1899 | Project Gutenberg #160 |
| The Woman in White | Wilkie Collins (†1889) | 1859 | Project Gutenberg #583 |
| The Moonstone | Wilkie Collins (†1889) | 1868 | Project Gutenberg #155 |
| Heart of Darkness | Joseph Conrad (†1924) | 1899 | Project Gutenberg #219 |
| Lord Jim | Joseph Conrad (†1924) | 1900 | Project Gutenberg #5658 |
| Nostromo | Joseph Conrad (†1924) | 1904 | Project Gutenberg #2021 |
| The Secret Agent | Joseph Conrad (†1924) | 1907 | Project Gutenberg #974 |
| The Last of the Mohicans | James Fenimore Cooper (†1851, †1945) | 1826 | Project Gutenberg #27681 |
| Maggie: A Girl of the Streets | Stephen Crane (†1900) | 1893 | Project Gutenberg #447 |
| The Red Badge of Courage | Stephen Crane (†1900) | 1895 | Project Gutenberg #73 |
| Two Years Before the Mast | Richard Henry Dana (†1882, †1938) | 1840 | Project Gutenberg #2055 |
| The Voyage of the Beagle | Charles Darwin (†1882) | 1839 | Project Gutenberg #944 |
| Robinson Crusoe | Daniel Defoe (†1731) | 1719 | Project Gutenberg #521 |
| Moll Flanders | Daniel Defoe (†1731) | 1722 | Project Gutenberg #370 |
| A Journal of the Plague Year | Daniel Defoe (†1731) | 1722 | Project Gutenberg #376 |
| The Pickwick Papers | Charles Dickens (†1870) | 1837 | Project Gutenberg #580 |
| Oliver Twist | Charles Dickens (†1870) | 1838 | Project Gutenberg #730 |
| Nicholas Nickleby | Charles Dickens (†1870) | 1839 | Project Gutenberg #967 |
| The Old Curiosity Shop | Charles Dickens (†1870) | 1841 | Project Gutenberg #700 |
| A Christmas Carol | Charles Dickens (†1870, †1864) | 1843 | Project Gutenberg #46 |
| Martin Chuzzlewit | Charles Dickens (†1870) | 1844 | Project Gutenberg #968 |
| Dombey and Son | Charles Dickens (†1870) | 1848 | Project Gutenberg #821 |
| David Copperfield | Charles Dickens (†1870) | 1850 | Project Gutenberg #766 |
| Bleak House | Charles Dickens (†1870) | 1853 | Project Gutenberg #1023 |
| Hard Times | Charles Dickens (†1870) | 1854 | Project Gutenberg #786 |
| Little Dorrit | Charles Dickens (†1870) | 1857 | Project Gutenberg #963 |
| A Tale of Two Cities | Charles Dickens (†1870) | 1859 | Project Gutenberg #98 |
| Great Expectations | Charles Dickens (†1870) | 1861 | Project Gutenberg #1400 |
| Our Mutual Friend | Charles Dickens (†1870) | 1865 | Project Gutenberg #883 |
| The Mystery of Edwin Drood | Charles Dickens (†1870) | 1870 | Project Gutenberg #564 |
| Notes from the Underground | Fyodor Dostoevsky (†1881, †1946) | 1864 | Project Gutenberg #600 |
| Crime and Punishment | Fyodor Dostoevsky (†1881, †1946) | 1866 | Project Gutenberg #2554 |
| The Possessed | Fyodor Dostoevsky (†1881, †1946) | 1872 | Project Gutenberg #8117 |
| The Brothers Karamazov | Fyodor Dostoevsky (†1881, †1946) | 1880 | Project Gutenberg #28054 |
| Narrative of the Life of Frederick Douglass | Frederick Douglass (†1895) | 1845 | Project Gutenberg #23 |
| A Study in Scarlet | Arthur Conan Doyle (†1930) | 1887 | Project Gutenberg #244 |
| The Sign of the Four | Arthur Conan Doyle (†1930) | 1890 | Project Gutenberg #2097 |
| The Adventures of Sherlock Holmes | Arthur Conan Doyle (†1930) | 1892 | Project Gutenberg #1661 |
| The Memoirs of Sherlock Holmes | Arthur Conan Doyle (†1930) | 1894 | Project Gutenberg #834 |
| The Hound of the Baskervilles | Arthur Conan Doyle (†1930) | 1902 | Project Gutenberg #2852 |
| The Return of Sherlock Holmes | Arthur Conan Doyle (†1930) | 1905 | Project Gutenberg #108 |
| The Lost World | Arthur Conan Doyle (†1930) | 1912 | Project Gutenberg #139 |
| The Valley of Fear | Arthur Conan Doyle (†1930) | 1915 | Project Gutenberg #3289 |
| His Last Bow | Arthur Conan Doyle (†1930) | 1917 | Project Gutenberg #2350 |
| Sister Carrie | Theodore Dreiser (†1945) | 1900 | Project Gutenberg #233 |
| The Aeneid | Virgil (translated by John Dryden) (†-19, †1700) | c. 19 BCE | Project Gutenberg #228 |
| The Count of Monte Cristo | Alexandre Dumas (†1870, †1888) | 1844 | Project Gutenberg #1184 |
| The Three Musketeers | Alexandre Dumas (†1870, †1888) | 1844 | Project Gutenberg #1257 |
| Twenty Years After | Alexandre Dumas (†1870, †1888) | 1845 | Project Gutenberg #1259 |
| The Man in the Iron Mask | Alexandre Dumas (†1870) | 1850 | Project Gutenberg #2759 |
| Adam Bede | George Eliot (†1880) | 1859 | Project Gutenberg #507 |
| The Mill on the Floss | George Eliot (†1880) | 1860 | Project Gutenberg #6688 |
| Silas Marner | George Eliot (†1880) | 1861 | Project Gutenberg #550 |
| Middlemarch | George Eliot (†1880) | 1872 | Project Gutenberg #145 |
| Daniel Deronda | George Eliot (†1880) | 1876 | Project Gutenberg #7469 |
| The Interesting Narrative of the Life of Olaudah Equiano | Olaudah Equiano (†1797) | 1789 | Project Gutenberg #15399 |
| Carmilla | Joseph Sheridan Le Fanu (†1873) | 1872 | Project Gutenberg #10007 |
| The History of Tom Jones, a Foundling | Henry Fielding (†1754) | 1749 | Project Gutenberg #6593 |
| This Side of Paradise | F. Scott Fitzgerald (†1940) | 1920 | Project Gutenberg #805 |
| The Great Gatsby | F. Scott Fitzgerald (†1940) | 1925 | Project Gutenberg #64317 |
| Madame Bovary | Gustave Flaubert (†1880, †1898) | 1857 | Project Gutenberg #2413 |
| The Good Soldier | Ford Madox Ford (†1939) | 1915 | Project Gutenberg #2775 |
| The Autobiography of Benjamin Franklin | Benjamin Franklin (†1790, †1926) | 1791 | Project Gutenberg #148 |
| The Man of Property | John Galsworthy (†1933) | 1906 | Project Gutenberg #2559 |
| Cranford | Elizabeth Gaskell (†1865, †1938) | 1853 | Project Gutenberg #394 |
| North and South | Elizabeth Gaskell (†1865) | 1855 | Project Gutenberg #4276 |
| Herland | Charlotte Perkins Gilman (†1935) | 1915 | Project Gutenberg #32 |
| Faust, Part 1 | Johann Wolfgang von Goethe (†1832, †1878, †1931) | 1808 | Project Gutenberg #14591 |
| The Vicar of Wakefield | Oliver Goldsmith (†1774) | 1766 | Project Gutenberg #2667 |
| The Wind in the Willows | Kenneth Grahame (†1932) | 1908 | Project Gutenberg #289 |
| Riders of the Purple Sage | Zane Grey (†1939) | 1912 | Project Gutenberg #1300 |
| Grimms' Fairy Tales | Jacob Grimm and Wilhelm Grimm (†1863, †1859) | 1812 | Project Gutenberg #2591 |
| King Solomon's Mines | H. Rider Haggard (†1925) | 1885 | Project Gutenberg #2166 |
| She | H. Rider Haggard (†1925) | 1887 | Project Gutenberg #3155 |
| Beowulf | Anonymous (translated by Lesslie Hall) (†1928) | 1000 | Project Gutenberg #16328 |
| Far from the Madding Crowd | Thomas Hardy (†1928) | 1874 | Project Gutenberg #27 |
| The Return of the Native | Thomas Hardy (†1928) | 1878 | Project Gutenberg #122 |
| The Mayor of Casterbridge | Thomas Hardy (†1928) | 1886 | Project Gutenberg #143 |
| Tess of the d'Urbervilles | Thomas Hardy (†1928) | 1891 | Project Gutenberg #110 |
| Jude the Obscure | Thomas Hardy (†1928) | 1895 | Project Gutenberg #153 |
| The Scarlet Letter | Nathaniel Hawthorne (†1864) | 1850 | Project Gutenberg #33 |
| The House of the Seven Gables | Nathaniel Hawthorne (†1864) | 1851 | Project Gutenberg #77 |
| The Prisoner of Zenda | Anthony Hope (†1933) | 1894 | Project Gutenberg #95 |
| The Rise of Silas Lapham | William Dean Howells (†1920) | 1885 | Project Gutenberg #154 |
| Tom Brown's School Days | Thomas Hughes (†1896) | 1857 | Project Gutenberg #1480 |
| Notre-Dame de Paris | Victor Hugo (†1885, †1928) | 1831 | Project Gutenberg #2610 |
| Les Misérables | Victor Hugo (†1885, †1928) | 1862 | Project Gutenberg #135 |
| The Legend of Sleepy Hollow | Washington Irving (†1859) | 1820 | Project Gutenberg #41 |
| Incidents in the Life of a Slave Girl | Harriet Jacobs (†1897, †1880) | 1861 | Project Gutenberg #11030 |
| Daisy Miller | Henry James (†1916) | 1878 | Project Gutenberg #208 |
| The Portrait of a Lady, Volume 1 | Henry James (†1916) | 1881 | Project Gutenberg #2833 |
| The Turn of the Screw | Henry James (†1916) | 1898 | Project Gutenberg #209 |
| The Ambassadors | Henry James (†1916) | 1903 | Project Gutenberg #432 |
| Ghost Stories of an Antiquary | M. R. James (†1936) | 1904 | Project Gutenberg #8486 |
| Three Men in a Boat | Jerome K. Jerome (†1927) | 1889 | Project Gutenberg #308 |
| Dubliners | James Joyce (†1941) | 1914 | Project Gutenberg #2814 |
| A Portrait of the Artist as a Young Man | James Joyce (†1941) | 1916 | Project Gutenberg #4217 |
| The Water-Babies | Charles Kingsley (†1875) | 1863 | Project Gutenberg #1018 |
| The Jungle Book | Rudyard Kipling (†1936) | 1894 | Project Gutenberg #236 |
| Captains Courageous | Rudyard Kipling (†1936) | 1897 | Project Gutenberg #2186 |
| Kim | Rudyard Kipling (†1936) | 1901 | Project Gutenberg #2226 |
| Just So Stories | Rudyard Kipling (†1936) | 1902 | Project Gutenberg #2781 |
| Sons and Lovers | D. H. Lawrence (†1930) | 1913 | Project Gutenberg #217 |
| The Rainbow | D. H. Lawrence (†1930) | 1915 | Project Gutenberg #28948 |
| Women in Love | D. H. Lawrence (†1930) | 1920 | Project Gutenberg #4240 |
| The Phantom of the Opera | Gaston Leroux (†1927) | 1910 | Project Gutenberg #175 |
| The Monk | Matthew Gregory Lewis (†1818) | 1796 | Project Gutenberg #601 |
| Main Street | Sinclair Lewis (†1951) | 1920 | Project Gutenberg #543 |
| Babbitt | Sinclair Lewis (†1951) | 1922 | Project Gutenberg #1156 |
| The Call of the Wild | Jack London (†1916) | 1903 | Project Gutenberg #215 |
| The Sea-Wolf | Jack London (†1916) | 1904 | Project Gutenberg #1074 |
| White Fang | Jack London (†1916) | 1906 | Project Gutenberg #910 |
| Martin Eden | Jack London (†1916) | 1909 | Project Gutenberg #1056 |
| The Great God Pan | Arthur Machen (†1947) | 1894 | Project Gutenberg #389 |
| Le Morte d'Arthur, Volume 1 | Thomas Malory (†1471) | 1485 | Project Gutenberg #1251 |
| The Beetle | Richard Marsh (†1915) | 1897 | Project Gutenberg #5164 |
| Moby-Dick; or, The Whale | Herman Melville (†1891) | 1851 | Project Gutenberg #2701 |
| Anne of Green Gables | L. M. Montgomery (†1942) | 1908 | Project Gutenberg #45 |
| Anne of Avonlea | L. M. Montgomery (†1942) | 1909 | Project Gutenberg #47 |
| Anne of the Island | L. M. Montgomery (†1942) | 1915 | Project Gutenberg #51 |
| Five Children and It | E. Nesbit (†1924) | 1902 | Project Gutenberg #778 |
| The Railway Children | E. Nesbit (†1924) | 1906 | Project Gutenberg #1874 |
| McTeague | Frank Norris (†1902) | 1899 | Project Gutenberg #165 |
| The Octopus | Frank Norris (†1902) | 1901 | Project Gutenberg #268 |
| The Scarlet Pimpernel | Baroness Orczy (†1947) | 1905 | Project Gutenberg #60 |
| The Oregon Trail | Francis Parkman (†1893) | 1849 | Project Gutenberg #1015 |
| Pollyanna | Eleanor H. Porter (†1920) | 1913 | Project Gutenberg #1450 |
| The Merry Adventures of Robin Hood | Howard Pyle (†1911) | 1883 | Project Gutenberg #964 |
| The Mysteries of Udolpho | Ann Radcliffe (†1823) | 1794 | Project Gutenberg #3268 |
| Ivanhoe | Walter Scott (†1832) | 1819 | Project Gutenberg #82 |
| Black Beauty | Anna Sewell (†1878) | 1877 | Project Gutenberg #271 |
| South: The Story of Shackleton's Last Expedition | Ernest Shackleton (†1922) | 1919 | Project Gutenberg #5199 |
| Pygmalion | George Bernard Shaw (†1950) | 1913 | Project Gutenberg #3825 |
| Frankenstein; or, The Modern Prometheus | Mary Wollstonecraft Shelley (†1851) | 1818 | Project Gutenberg #84 |
| The Last Man | Mary Wollstonecraft Shelley (†1851) | 1826 | Project Gutenberg #18247 |
| Quo Vadis | Henryk Sienkiewicz (†1916, †1906) | 1896 | Project Gutenberg #2853 |
| The Expedition of Humphry Clinker | Tobias Smollett (†1771) | 1771 | Project Gutenberg #2160 |
| The Life and Opinions of Tristram Shandy | Laurence Sterne (†1768) | 1759 | Project Gutenberg #1079 |
| Travels with a Donkey in the Cévennes | Robert Louis Stevenson (†1894, †1915) | 1879 | Project Gutenberg #535 |
| Treasure Island | Robert Louis Stevenson (†1894, †1926) | 1883 | Project Gutenberg #120 |
| The Strange Case of Dr Jekyll and Mr Hyde | Robert Louis Stevenson (†1894) | 1886 | Project Gutenberg #43 |
| Kidnapped | Robert Louis Stevenson (†1894) | 1886 | Project Gutenberg #421 |
| The Black Arrow | Robert Louis Stevenson (†1894) | 1888 | Project Gutenberg #848 |
| The Master of Ballantrae | Robert Louis Stevenson (†1894) | 1889 | Project Gutenberg #864 |
| Dracula | Bram Stoker (†1912) | 1897 | Project Gutenberg #345 |
| Uncle Tom's Cabin | Harriet Beecher Stowe (†1896) | 1852 | Project Gutenberg #203 |
| Gulliver's Travels | Jonathan Swift (†1745) | 1726 | Project Gutenberg #829 |
| Vanity Fair | William Makepeace Thackeray (†1863) | 1848 | Project Gutenberg #599 |
| War and Peace | Leo Tolstoy (†1910, †1938, †1939) | 1869 | Project Gutenberg #2600 |
| Anna Karenina | Leo Tolstoy (†1910, †1946) | 1878 | Project Gutenberg #1399 |
| The Warden | Anthony Trollope (†1882) | 1855 | Project Gutenberg #619 |
| Barchester Towers | Anthony Trollope (†1882) | 1857 | Project Gutenberg #3409 |
| The Way We Live Now | Anthony Trollope (†1882) | 1875 | Project Gutenberg #5231 |
| The Innocents Abroad | Mark Twain (†1910) | 1869 | Project Gutenberg #3176 |
| Roughing It | Mark Twain (†1910) | 1872 | Project Gutenberg #3177 |
| The Adventures of Tom Sawyer | Mark Twain (†1910) | 1876 | Project Gutenberg #74 |
| A Tramp Abroad | Mark Twain (†1910) | 1880 | Project Gutenberg #119 |
| The Prince and the Pauper | Mark Twain (†1910) | 1881 | Project Gutenberg #1837 |
| Life on the Mississippi | Mark Twain (†1910) | 1883 | Project Gutenberg #245 |
| Adventures of Huckleberry Finn | Mark Twain (†1910, †1933) | 1884 | Project Gutenberg #76 |
| A Connecticut Yankee in King Arthur's Court | Mark Twain (†1910) | 1889 | Project Gutenberg #86 |
| From the Earth to the Moon | Jules Verne (†1905) | 1865 | Project Gutenberg #83 |
| Twenty Thousand Leagues under the Sea | Jules Verne (†1905) | 1870 | Project Gutenberg #164 |
| Around the World in Eighty Days | Jules Verne (†1905, †1893) | 1873 | Project Gutenberg #103 |
| The Mysterious Island | Jules Verne (†1905, †1913) | 1874 | Project Gutenberg #1268 |
| Ben-Hur: A Tale of the Christ | Lew Wallace (†1905) | 1880 | Project Gutenberg #2145 |
| The Castle of Otranto | Horace Walpole (†1797, †1894) | 1764 | Project Gutenberg #696 |
| Up from Slavery | Booker T. Washington (†1915) | 1901 | Project Gutenberg #2376 |
| Daddy-Long-Legs | Jean Webster (†1916) | 1912 | Project Gutenberg #157 |
| The Time Machine | H. G. Wells (†1946) | 1895 | Project Gutenberg #35 |
| The Island of Doctor Moreau | H. G. Wells (†1946) | 1896 | Project Gutenberg #159 |
| The Invisible Man | H. G. Wells (†1946) | 1897 | Project Gutenberg #5230 |
| The War of the Worlds | H. G. Wells (†1946) | 1898 | Project Gutenberg #36 |
| The First Men in the Moon | H. G. Wells (†1946) | 1901 | Project Gutenberg #1013 |
| The Sleeper Awakes | H. G. Wells (†1946) | 1910 | Project Gutenberg #12163 |
| The House of Mirth | Edith Wharton (†1937) | 1905 | Project Gutenberg #284 |
| Ethan Frome | Edith Wharton (†1937) | 1911 | Project Gutenberg #4517 |
| The Age of Innocence | Edith Wharton (†1937) | 1920 | Project Gutenberg #541 |
| The Happy Prince and Other Tales | Oscar Wilde (†1900) | 1888 | Project Gutenberg #902 |
| The Picture of Dorian Gray | Oscar Wilde (†1900) | 1890 | Project Gutenberg #174 |
| Lady Windermere's Fan | Oscar Wilde (†1900) | 1892 | Project Gutenberg #790 |
| The Importance of Being Earnest | Oscar Wilde (†1900) | 1895 | Project Gutenberg #844 |
| An Ideal Husband | Oscar Wilde (†1900) | 1895 | Project Gutenberg #885 |
| The Virginian | Owen Wister (†1938) | 1902 | Project Gutenberg #1298 |
| The Voyage Out | Virginia Woolf (†1941) | 1915 | Project Gutenberg #144 |
| Night and Day | Virginia Woolf (†1941) | 1919 | Project Gutenberg #1245 |
| Jacob's Room | Virginia Woolf (†1941) | 1922 | Project Gutenberg #5670 |
| Mrs Dalloway in Bond Street | Virginia Woolf (†1941) | 1923 | Project Gutenberg #63107 |
| Tibullus: Elegiae (Latin) | Albius Tibullus | c. 19 BCE | Perseus, ed. Postgate 1915 (CC BY-SA 4.0) |
| Catullus: Carmina (Latin) | C. Valerius Catullus | c. 54 BCE | Perseus, ed. Merrill 1893 (CC BY-SA 4.0) |
| Valerius Flaccus: Argonautica (Latin) | C. Valerius Flaccus | c. 90 CE | Perseus, ed. Kramer 1913 (CC BY-SA 4.0) |
| Lucan: Pharsalia (Bellum civile) (Latin) | M. Annaeus Lucanus | c. 65 CE | Perseus, ed. Weise 1835 (CC BY-SA 4.0) |
| Cicero: Pro Sexto Roscio Amerino (Latin) | M. Tullius Cicero | c. 80 BCE | Perseus, ed. Clark 1908 (CC BY-SA 4.0) |
| Cicero: In Verrem (Latin) | M. Tullius Cicero | c. 70 BCE | Perseus, ed. Peterson 1917 (CC BY-SA 4.0) |
| Cicero: De imperio Cn. Pompei (Latin) | M. Tullius Cicero | c. 66 BCE | Perseus, ed. Clark 1908 (CC BY-SA 4.0) |
| Cicero: Pro Murena (Latin) | M. Tullius Cicero | c. 63 BCE | Perseus, ed. Clark 1908 (CC BY-SA 4.0) |
| Cicero: Pro Archia poeta (Latin) | M. Tullius Cicero | c. 62 BCE | Perseus, ed. Clark 1911 (CC BY-SA 4.0) |
| Cicero: Epistulae ad Atticum (Latin) | M. Tullius Cicero | c. 61 BCE | Perseus, ed. Purser 1903 (CC BY-SA 4.0) |
| Cicero: Pro Caelio (Latin) | M. Tullius Cicero | c. 56 BCE | Perseus, ed. Clark 1908 (CC BY-SA 4.0) |
| Cicero: Pro Sestio (Latin) | M. Tullius Cicero | c. 56 BCE | Perseus, ed. Peterson 1909 (CC BY-SA 4.0) |
| Cicero: De oratore (Latin) | M. Tullius Cicero | c. 55 BCE | Perseus, ed. Wilkins 1902 (CC BY-SA 4.0) |
| Cicero: Epistulae ad Quintum fratrem (Latin) | M. Tullius Cicero | c. 55 BCE | Perseus, ed. Purser 1903 (CC BY-SA 4.0) |
| Cicero: Pro Milone (Latin) | M. Tullius Cicero | c. 52 BCE | Perseus, ed. Clark 1918 (CC BY-SA 4.0) |
| Cicero: De re publica (Latin) | M. Tullius Cicero | c. 51 BCE | Perseus, ed. Mueller 1889 (CC BY-SA 4.0) |
| Cicero: Epistulae ad familiares (Latin) | M. Tullius Cicero | c. 50 BCE | Perseus, ed. Purser 1901 (CC BY-SA 4.0) |
| Cicero: Brutus (Latin) | M. Tullius Cicero | c. 46 BCE | Perseus, ed. Wilkins 1902 (CC BY-SA 4.0) |
| Cicero: De optimo genere oratorum (Latin) | M. Tullius Cicero | c. 46 BCE | Perseus, ed. Wilkins 1902 (CC BY-SA 4.0) |
| Cicero: Orator (Latin) | M. Tullius Cicero | c. 46 BCE | Perseus, ed. Wilkins 1902 (CC BY-SA 4.0) |
| Cicero: Paradoxa Stoicorum (Latin) | M. Tullius Cicero | c. 46 BCE | Perseus, ed. Kayser & Baiter 1864 (CC BY-SA 4.0) |
| Cicero: Academica (Latin) | M. Tullius Cicero | c. 45 BCE | Perseus, ed. Plasberg 1922 (CC BY-SA 4.0) |
| Cicero: De finibus bonorum et malorum (Latin) | M. Tullius Cicero | c. 45 BCE | Perseus, ed. Schiche 1915 (CC BY-SA 4.0) |
| Cicero: De natura deorum (Latin) | M. Tullius Cicero | c. 45 BCE | Perseus, ed. Plasberg 1917 (CC BY-SA 4.0) |
| Cicero: Lucullus (Academica priora) (Latin) | M. Tullius Cicero | c. 45 BCE | Perseus, ed. Plasberg 1922 (CC BY-SA 4.0) |
| Cicero: Tusculanae disputationes (Latin) | M. Tullius Cicero | c. 45 BCE | Perseus, ed. Pohlenz 1918 (CC BY-SA 4.0) |
| Cicero: Cato maior de senectute (Latin) | M. Tullius Cicero | c. 44 BCE | Perseus, ed. Falconer 1923 (CC BY-SA 4.0) |
| Cicero: De divinatione (Latin) | M. Tullius Cicero | c. 44 BCE | Perseus, ed. Müller 1915 (CC BY-SA 4.0) |
| Cicero: De officiis (Latin) | M. Tullius Cicero | c. 44 BCE | Perseus, ed. Miller 1928 (CC BY-SA 4.0) |
| Cicero: Laelius de amicitia (Latin) | M. Tullius Cicero | c. 44 BCE | Perseus, ed. Falconer 1923 (CC BY-SA 4.0) |
| Cicero: Philippicae (Latin) | M. Tullius Cicero | c. 44 BCE | Perseus, ed. Clark 1918 (CC BY-SA 4.0) |
| Cicero: Epistulae ad Brutum (Latin) | M. Tullius Cicero | c. 43 BCE | Perseus, ed. Purser 1903 (CC BY-SA 4.0) |
| Cicero: In Catilinam I–IV (Latin) | M. Tullius Cicero | c. 63 BCE | Perseus, ed. Clark 1908 (CC BY-SA 4.0) |
| Ovid: Amores (Latin) | P. Ovidius Naso | c. 16 BCE | Perseus, ed. Ehwald 1907 (CC BY-SA 4.0) |
| Ovid: Heroides (Latin) | P. Ovidius Naso | c. 15 BCE | Perseus, ed. Ehwald 1907 (CC BY-SA 4.0) |
| Ovid: Medicamina faciei femineae (Latin) | P. Ovidius Naso | c. 1 BCE | Perseus, ed. Ehwald 1907 (CC BY-SA 4.0) |
| Ovid: Ars amatoria (Latin) | P. Ovidius Naso | c. 2 CE | Perseus, ed. Ehwald 1907 (CC BY-SA 4.0) |
| Ovid: Remedia amoris (Latin) | P. Ovidius Naso | c. 2 CE | Perseus, ed. Ehwald 1907 (CC BY-SA 4.0) |
| Ovid: Metamorphoses (Latin) | P. Ovidius Naso | c. 8 CE | Perseus, ed. Magnus 1892 (CC BY-SA 4.0) |
| Ovid: Ibis (Latin) | P. Ovidius Naso | c. 10 CE | Perseus, ed. Ehwald 1889 (CC BY-SA 4.0) |
| Statius: Thebaid (Latin) | P. Papinius Statius | c. 92 CE | Perseus, ed. Mozley 1928 (CC BY-SA 4.0) |
| Vergil: Eclogues (Latin) | P. Vergilius Maro | c. 38 BCE | Perseus, ed. Greenough 1881 (CC BY-SA 4.0) |
| Vergil: Georgics (Latin) | P. Vergilius Maro | c. 29 BCE | Perseus, ed. Greenough 1881 (CC BY-SA 4.0) |
| Vergil: Aeneid (Latin) | P. Vergilius Maro | c. 19 BCE | Perseus, ed. Greenough 1881 (CC BY-SA 4.0) |
| Horace: Epodes (Latin) | Q. Horatius Flaccus | c. 30 BCE | Perseus, ed. Vollmer 1912 (CC BY-SA 4.0) |
| Horace: Satires (Latin) | Q. Horatius Flaccus | c. 30 BCE | Perseus, ed. Smart 1836 (CC BY-SA 4.0) |
| Horace: Carmina (Odes) (Latin) | Q. Horatius Flaccus | c. 23 BCE | Perseus, ed. Laing & Shorey 1919 (CC BY-SA 4.0) |
| Horace: Epistles (Latin) | Q. Horatius Flaccus | c. 20 BCE | Perseus, ed. Fairclough 1929 (CC BY-SA 4.0) |
| Horace: Ars poetica (Latin) | Q. Horatius Flaccus | c. 19 BCE | Perseus, ed. Smart 1836 (CC BY-SA 4.0) |
| Horace: Carmen saeculare (Latin) | Q. Horatius Flaccus | c. 17 BCE | Perseus, ed. Laing & Shorey 1919 (CC BY-SA 4.0) |
| Sallust: De Catilinae coniuratione (Latin) | C. Sallustius Crispus | c. 41 BCE | Perseus, ed. Ahlberg 1919 (CC BY-SA 4.0) |
| Propertius: Elegiae (Latin) | Sex. Propertius | c. 16 BCE | Perseus, ed. Mueller 1898 (CC BY-SA 4.0) |

291 corpora

**Rights.** An English work is admitted only when every author, translator *and* other contributor (editor, illustrator, author of an introduction) died in 1955 or earlier
(so the 70-year term after death has expired in the EU) and the text was first published before
1931 (so it is public domain in the US). `backend/scripts/verify_catalogue.py` checks each entry
against Project Gutenberg's RDF metadata (names, death years, language, rights statement) and
records the result in the catalogue (`people`, `verified`); `build_gutenberg_seeds.py` refuses
entries that failed the check. Regenerate the English seeds with
`backend/scripts/build_gutenberg_seeds.py` (catalogue in `backend/data/catalogue/gutenberg.json`),
the table above with `backend/scripts/readme_catalogue.py`, and the Latin seeds with
`backend/scripts/build_perseus_seed.py --batch 1` (or `--corpus <slug>`; rights check: `verify_perseus.py`, list of works: [docs/latin-works.md](docs/latin-works.md))
(needs the LatinCy wheel, see below); Latin corpora come only from printed editions published
before 1931. The Latin texts are CC BY-SA 4.0 from the Perseus Digital Library. Afterwards run
`backend/scripts/patch_seed_metadata.py`, which writes each corpus's source, licence and rights
statement (shown in the reader's Details tab).

## Building a seed corpus

```bash
cd backend
.venv/bin/python scripts/build_seed.py data/seed/my-text.txt --slug my-text --title "My Text" --extractor spacy
```

The resulting `data/seed/my-text.json` (or `.json.gz` with `--gzip`) is imported automatically at startup.

Latin (or other languages) work with any spaCy pipeline that provides NER, e.g. LatinCy:

```bash
uv pip install https://huggingface.co/latincy/la_core_web_md/resolve/main/la_core_web_md-3.9.8-py3-none-any.whl
.venv/bin/python scripts/build_seed.py vergil.txt --slug vergil --title "Aeneid" --language la \
  --extractor spacy --spacy-model la_core_web_md --spacy-labels PERSON,LOC,NORP --gzip
```

## License

The code is MIT-licensed. The bundled corpora are not covered by the MIT licence; see
[`backend/data/seed/NOTICE.md`](backend/data/seed/NOTICE.md):

- **English works**: public domain in the EU and the US. Every author and translator died in 1955
  or earlier, and every work was first published before 1931. Project Gutenberg's licence,
  trademark and volunteer notes are removed. The derived annotations are MIT-licensed.
- **Latin works** (Vergil, Cicero, Horace, Ovid and others; see [docs/latin-works.md](docs/latin-works.md)): the
  Perseus Digital Library editions are licensed CC BY-SA 4.0. The adapted corpora, including their
  annotations, are shared under the same licence.
