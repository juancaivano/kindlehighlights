def get_readwise_books(self) -> Dict[int, Dict]:
    """Fetch full book objects from Readwise API with pagination support"""
    url = "https://readwise.io/api/v2/books/"
    headers = {"Authorization": f"Token {self.readwise_token}"}
    params = {"page_size": 1000}

    all_books = {}

    try:
        while url:
            logger.info(f"Fetching books from: {url}")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            books = data.get("results", [])

            for book in books:
                all_books[book["id"]] = book  # store full book dict

            url = data.get("next")
            params = {}  # clear for subsequent pages

            logger.info(f"Fetched {len(books)} books. Total: {len(all_books)}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching books: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching books: {e}")
        return {}

    logger.info(f"Successfully fetched {len(all_books)} total books")
    return all_books
