import os
from difflib import SequenceMatcher

import nltk
import pandas
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, render_template, request
from loguru import logger

# tester
# ======

nltk.download("stopwords")
nltk.download("punkt")
nltk.download("punkt_tab")
stop_words = set(nltk.corpus.stopwords.words("english"))


def purify_text(string: str) -> str:
    """Clear text."""
    words = nltk.word_tokenize(string)
    return " ".join([word for word in words if word not in stop_words])


def web_verify(string: str, results_per_sentence: str) -> list:
    """Web verify function."""
    matching_sites = [url for url in search(query=string, num=results_per_sentence)]

    sentences = nltk.sent_tokenize(string)
    for sentence in sentences:
        for url in search(query=sentence, num=results_per_sentence):
            matching_sites.append(url)

    return list(set(matching_sites))


def similarity(str1: str, str2: str) -> float:
    """Calculate the similarity in percentages."""
    return (SequenceMatcher(None, str1, str2).ratio()) * 100


def report(text: str) -> dict:
    """Forming a report."""
    matching_sites = web_verify(purify_text(text), 2)
    matches = {}

    for i in range(len(matching_sites)):
        matches[matching_sites[i]] = similarity(
            text,
            extract_text(matching_sites[i]),
        )

    return {
        k: v for k, v in sorted(matches.items(), key=lambda item: item[1], reverse=True)
    }


def return_table(dictionary: dict) -> str:
    """Return the table."""
    search_result = pandas.DataFrame({"Similarity (%)": dictionary})
    return search_result.to_html()


# Search util
# ===========


def search(query: str, num: int) -> list[str]:
    """Do a request and collecting result."""
    user_agent = os.getenv("USER_AGENT")
    search_link = os.getenv("SEARCH_LINK")
    cookie = os.getenv("COOKIE")
    user_black_list = os.getenv("BLACK_LIST").split(", ")

    black_list = [
        # Yandex black list
        "https://passport.yandex.ru/",
        "https://yandexwebcache.net/",
        "https://yandex.ru/support/",
        "https://cloud.yandex.ru/",
        "https://yandex.ru/",
        "https://www.ya.ru",
    ]

    black_list.extend(user_black_list)

    url = f"{search_link}{query}"
    urls = []

    page = requests.get(
        url,
        headers={
            "user-agent": user_agent,
            "cookie": cookie,
        },
        timeout=20,
    )
    soup = BeautifulSoup(page.text, "html.parser")

    for link in soup.find_all("a"):
        url = str(link.get("href"))

        black = False
        if url.startswith("http"):
            for black_url in black_list:
                if black_url in url:
                    black = True
                    break
            if not black:
                urls.append(url)
                logger.debug("URL: {}", url)
            else:
                logger.error("URL: {}", url)

    return urls[:num]


def extract_text(url: str) -> str:
    """Extract text from url."""
    page = requests.get(url, timeout=40)
    soup = BeautifulSoup(page.text, "html.parser")
    return soup.get_text()


# Web app
# =======

app = Flask(__name__, template_folder="Templates")


@app.route("/", methods=["GET", "POST"])
def main_page() -> str:
    """Render and return main page."""
    return render_template("index.html")


@app.route("/report", methods=["POST", "GET"])
def report_page() -> str:
    """Render and return report page."""
    result = request.form["text"]
    return render_template("report.html") + return_table(
        report(str(result)),
    )


if __name__ == "__main__":
    # Loading consts from .env
    load_dotenv()

    IS_DEBUG = os.getenv("DEBUG").lower() == "true"
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")

    # Starting flask app
    app.run(debug=IS_DEBUG, host=HOST, port=PORT)
