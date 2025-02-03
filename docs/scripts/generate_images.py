import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def generate_screenshot_from_browser(
    url: str,
    output_path: str,
    selector: Optional[str] = None,
    viewport_size: Optional[tuple[int, int]] = None,
    clicks: Optional[list[str]] = None,
    delay: Optional[float] = None,
    local_storage: Optional[dict[str, str]] = None,
    zoom: Optional[float] = None,
) -> None:
    """
    Generate a screenshot from a web page using a headless browser.

    This function loads the specified URL in a headless browser, optionally performs
    a series of clicks, selects a specific DOM element, and captures a screenshot.
    The screenshot is then saved to the specified output path.

    Args:
        url (str): The URL of the web page to capture.
        output_path (str): The file path where the screenshot will be saved.
        selector (Optional[str]): A CSS selector to capture a specific element.
            If None, captures the entire page. Defaults to None.
        viewport_size (Optional[Tuple[int, int]]): The size of the browser viewport
            as a tuple of (width, height) in pixels. If None, uses the default size.
        clicks (Optional[List[str]]): A list of CSS selectors for elements to click
            before taking the screenshot.
        delay (Optional[float]): The number of seconds to wait before taking the
            screenshot after all other actions are completed.
        local_storage (Optional[dict[str, str]]): A dictionary of key-value pairs to set
            in local storage before loading the page.
        zoom (Optional[float]): The zoom level to set for the page. If None, uses the default zoom.

    Raises:
        Exception: If there's an error during the browser interaction or screenshot capture.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        if viewport_size:
            await page.set_viewport_size(
                {"width": viewport_size[0], "height": viewport_size[1]}
            )

        if local_storage:
            await context.add_init_script(
                f"""
                Object.assign(window.localStorage, {json.dumps(local_storage)});
            """
            )

        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            if zoom:
                await page.evaluate(f"document.body.style.zoom = {zoom}")

            if clicks:
                for click_selector in clicks:
                    elements = await page.query_selector_all(click_selector)
                    for element in elements:
                        await element.click()
                    await page.wait_for_load_state("networkidle")

            if delay:
                await asyncio.sleep(delay)

            if selector:
                element = await page.query_selector(selector)
                if element:
                    await element.screenshot(path=output_path)
                else:
                    raise ValueError(f"Element with selector '{selector}' not found")
            else:
                await page.screenshot(path=output_path, full_page=True)

            logging.info(f"Screenshot captured successfully: {output_path}")

        except Exception as e:
            logging.exception(f"Error capturing screenshot for {url}: {str(e)}")
            raise

        finally:
            await browser.close()


def generate_screenshot(screenshot_spec):
    try:
        asyncio.run(
            generate_screenshot_from_browser(
                screenshot_spec["url"],
                screenshot_spec["output_path"],
                selector=screenshot_spec.get("selector"),
                viewport_size=tuple(screenshot_spec.get("viewport_size", [])),
                clicks=screenshot_spec.get("clicks"),
                delay=screenshot_spec.get("delay"),
                local_storage=screenshot_spec.get("local_storage"),
                zoom=screenshot_spec.get("zoom"),
            )
        )
    except Exception as e:
        logging.exception(f"Failed to generate screenshot: {str(e)}")


def generate_screenshots_from_spec(spec_filepath):
    try:
        with open(spec_filepath) as f:
            spec = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.exception(f"Error reading or parsing spec file: {str(e)}")
        return

    with ThreadPoolExecutor() as executor:
        executor.map(generate_screenshot, spec["screenshots"])


if __name__ == "__main__":
    generate_screenshots_from_spec("./scripts/screenshot_spec.json")
