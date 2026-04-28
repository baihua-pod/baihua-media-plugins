# Scraping Fallback Chain

When scraping an article URL, try each method in order. Stop at the first success.

## 1. Jina Reader

```
WebFetch("https://r.jina.ai/<URL>")
```

Best for non-paywalled sites. Returns clean markdown. Fails with 403/451 on paywalled sites (NYT, WSJ, WaPo, AP).

## 2. WebFetch Direct

```
WebFetch("<URL>")
```

Sometimes works when Jina is blocked. Returns raw HTML — extract article text from the response.

## 3. Edge AppleScript (Chunked)

Works for paywalled sites if the user is logged in via browser. **Always use chunked reads** — bare `document.body.innerText` truncates at ~4000-6000 chars.

```bash
# Open page and wait for load
open -a "Microsoft Edge" "URL"
sleep 6

# Check total length
osascript -e 'tell application "Microsoft Edge" to execute active tab of first window javascript "document.body.innerText.length"'

# Read in 6000-char chunks
osascript -e 'tell application "Microsoft Edge" to execute active tab of first window javascript "document.body.innerText.substring(0, 6000)"'
osascript -e 'tell application "Microsoft Edge" to execute active tab of first window javascript "document.body.innerText.substring(6000, 12000)"'
osascript -e 'tell application "Microsoft Edge" to execute active tab of first window javascript "document.body.innerText.substring(12000, 18000)"'
# Continue until chunk is empty or shorter than 6000 chars
```

Most articles fit in 2-3 chunks. Very long articles (>18k chars) may need 4+.

## 4. Last Resort

If all methods fail: translate with whatever content is available, set `thin_content: true` in frontmatter so review can flag it.
