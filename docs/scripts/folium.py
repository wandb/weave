import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def slam_webpage(url: str, num_requests: int) -> None:
    """
    Slam a webpage by making a specified number of requests to it.

    Args:
        url (str): The URL of the web page to slam.
        num_requests (int): The number of requests to make to the web page.

    Raises:
        Exception: If there's an error during the requests.
    """
    def make_request():
        try:
            response = requests.get(url)
            if response.status_code == 200:
                logging.info(f"Request to {url} completed successfully")
            else:
                logging.error(f"Request to {url} failed with status code {response.status_code}")
        except Exception as e:
            logging.error(f"Error slamming webpage {url}: {str(e)}")
            raise

    with ThreadPoolExecutor(max_workers=1000) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error in future: {str(e)}")

if __name__ == "__main__":
    # Example usage: slam a webpage with 10000 requests
    slam_webpage("https://ecodraw.io", 10000)
