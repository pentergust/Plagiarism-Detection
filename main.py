from difflib import SequenceMatcher

import nltk
import pandas
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from loguru import logger
from pydantic_settings import BaseSettings

# Global config
# =============


class Config(BaseSettings):
    """Setting for webapp.

    Loaded once on start app from .env file.
    """

    user_agent: str
    search_link: str
    cookie: str
    black_list: str

    # Flask settings
    debug: bool
    host: str
    port: int


URL_BLACKLIST = [
    # Yandex black list
    "https://passport.yandex.ru/",
    "https://yandexwebcache.net/",
    "https://yandex.ru/support/",
    "https://cloud.yandex.ru/",
    "https://yandex.ru/",
    "https://www.ya.ru",
]

config = Config(_env_file=".env")
URL_BLACKLIST.extend(config.black_list.split(", "))

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
    urls = []

    page = requests.get(
        url=f"{config.search_link}/{query}",
        headers={
            "user-agent": config.user_agent,
            "cookie": config.cookie,
        },
        timeout=20,
    )
    soup = BeautifulSoup(page.text, "html.parser")

    for link in soup.find_all("a"):
        url = str(link.get("href"))

        black = False
        if url.startswith("http"):
            for black_url in URL_BLACKLIST:
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


app.run(debug=config.debug, host=config.host, port=config.port)
