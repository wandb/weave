# Synthetic data for model monitoring

import datetime
import tqdm
import os
import numpy as np
import pandas as pd
import random
from faker import Faker
from weave.ops_arrow.list_ import dataframe_to_arrow
from datetime import timedelta, time
from weave import ops_arrow

# Generate the version schedule
def generate_version_schedule(
    start_date: datetime.datetime, end_date: datetime.datetime
) -> dict:
    current_date = start_date
    versions = ["1.0"]
    version_schedule = {}
    while current_date <= end_date:
        date_versions = []
        for version in versions:
            service_percent = random.uniform(0, 1)
            date_versions.append((version, service_percent))

        version_schedule[current_date.date()] = date_versions
        current_date += timedelta(days=1)
        if random.random() < 0.10:  # 5% chance to introduce a new version each day
            new_version = f"{float(versions[-1])+0.1:.1f}"
            versions.append(new_version)
        if len(versions) > 1 and random.random() < 0.10:
            versions.pop(0)
    return version_schedule


# Generate the latency schedule
def generate_latency_schedule(
    start_date: datetime.datetime, end_date: datetime.datetime
) -> dict:
    latency_schedule = {}
    for current_date in pd.date_range(start_date, end_date):
        base_latency = random.uniform(0.1, 1)
        day_factor = random.uniform(0.5, 1.5)
        month_factor = random.uniform(0.5, 1.5)
        latency = base_latency * day_factor * month_factor
        latency_schedule[current_date.date()] = latency
    return latency_schedule


# Generate the cost schedule
def generate_cost_schedule(
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    cost_change_date: datetime.datetime,
) -> dict:
    cost_schedule = {}
    current_date = start_date
    cost_per_token = 0.01
    while current_date <= end_date:
        if current_date >= cost_change_date:
            cost_per_token = 0.005
        cost_schedule[current_date.date()] = cost_per_token
        current_date += timedelta(days=1)
    return cost_schedule


def generate_user_usage_schedule(
    start_date: datetime.datetime, end_date: datetime.datetime, users: list
) -> list:
    user_usage_schedule = []
    for user in users:
        current_date = start_date + timedelta(days=random.randrange(90))
        while current_date <= end_date:
            usage_periods = random.randint(1, 30)
            for _ in range(usage_periods):
                period_length_timedelta = timedelta(hours=random.randint(1, 24 * 7))
                rate = random.uniform(0.1, 10)
                user_usage_schedule.append(
                    (current_date, user, period_length_timedelta, rate)
                )
                current_date += period_length_timedelta  # Increment current_date
                if current_date > end_date:
                    break
    return user_usage_schedule


def random_predictions(n_users: int = 10) -> ops_arrow.ArrowWeaveList:
    # Define our fake users
    fake = Faker()
    users = [fake.user_name() for _ in range(n_users)]

    # Read the file and generate prompts
    with open(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "testdata/t8.shakespeare.txt")
        ),
        "r",
    ) as f:
        lines = f.read().split("\n")

    # Define the time range
    start_date = pd.to_datetime("2023-01-01", utc=True)
    end_date = pd.to_datetime("2023-03-31", utc=True)
    cost_change_date = pd.to_datetime("2023-02-15", utc=True)

    # Generate the schedules
    version_schedule = generate_version_schedule(start_date, end_date)
    latency_schedule = generate_latency_schedule(start_date, end_date)
    cost_schedule = generate_cost_schedule(start_date, end_date, cost_change_date)
    user_usage_schedule = generate_user_usage_schedule(start_date, end_date, users)

    # Helper function to generate a random completion
    def generate_completion(prompt: str) -> str:
        words = prompt.split()
        completion = " ".join(
            random.choices(words, k=int(len(words) * (random.random() + 0.1) * 10))
        )
        return completion

    data = []
    for usage in tqdm.tqdm(user_usage_schedule):
        usage_date, user, usage_period, rate = usage

        end_date = usage_date + usage_period
        increment = timedelta(hours=rate)

        while usage_date < end_date:
            # Find the version that was active during this usage
            if usage_date.date() not in version_schedule:
                break
            active_versions = version_schedule[usage_date.date()]
            # active_versions = [(version, percent) for date, version, percent in version_schedule if date.date() == usage_date.date()]
            # Normalize the service percentages
            total_percent = sum([percent for version, percent in active_versions])
            if total_percent == 0:
                continue
            normalized_percentages = [
                percent / total_percent for version, percent in active_versions
            ]

            version = np.random.choice(
                [v for v, p in active_versions], p=normalized_percentages
            )

            # Find the cost during this usage
            cost_per_token = cost_schedule[usage_date.date()]

            # Find the average latency during this usage
            latency = latency_schedule[usage_date.date()]
            latency *= 0.9 + random.random() * 0.2

            prompt = " ".join(random.sample(lines, 10))  # Increase prompt size
            completion = generate_completion(prompt)
            prompt_tokens = len(prompt.split())
            completion_tokens = len(completion.split())
            api_cost = (prompt_tokens + completion_tokens) * cost_per_token

            data.append(
                [
                    usage_date,
                    user,
                    version,
                    prompt,
                    completion,
                    prompt_tokens,
                    completion_tokens,
                    api_cost,
                    latency,
                ]
            )

            usage_date += increment

    df = pd.DataFrame(
        data,
        columns=[
            "timestamp",
            "username",
            "model_version",
            "prompt",
            "completion",
            "prompt_tokens",
            "completion_tokens",
            "api_cost",
            "latency",
        ],
    )
    return dataframe_to_arrow(df)  # type: ignore
