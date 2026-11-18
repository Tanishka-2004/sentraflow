"""
Realistic Indian Financial Data Generator.

Generates synthetic customers, accounts, merchants, and transactions with:
- Strict Verhoeff-failing synthetic 12-digit Aadhaar IDs.
- Valid & intentionally malformed PAN numbers (format AAAAA9999A).
- Realistic Indian banking channels (UPI, CARD, NEFT, IMPS, ATM) & INR amounts.
- Seeded, configurable volume and deterministic reproducibility.
- Realistic dirty data injection (nulls, malformed formats, duplicates, schema drift).
- Complex fraud pattern injection (velocity, impossible travel, night spike, card testing).
- SCD Type 2 mutation generator.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import numpy as np
from faker import Faker

from data_generator.entities import Account, Customer, Merchant, Transaction
from data_generator.verhoeff import generate_invalid_verhoeff_12_digit


class CityInfo(TypedDict):
    city: str
    state: str
    lat: float
    lon: float
    pincode_prefix: str


class MccInfo(TypedDict):
    mcc: str
    category: str
    risk: str


# Major Indian Cities and coordinates
INDIAN_CITIES: list[CityInfo] = [
    {
        "city": "Mumbai",
        "state": "Maharashtra",
        "lat": 19.0760,
        "lon": 72.8777,
        "pincode_prefix": "400",
    },
    {
        "city": "Delhi",
        "state": "Delhi",
        "lat": 28.7041,
        "lon": 77.1025,
        "pincode_prefix": "110",
    },
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "lat": 12.9716,
        "lon": 77.5946,
        "pincode_prefix": "560",
    },
    {
        "city": "Hyderabad",
        "state": "Telangana",
        "lat": 17.3850,
        "lon": 78.4867,
        "pincode_prefix": "500",
    },
    {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "lat": 13.0827,
        "lon": 80.2707,
        "pincode_prefix": "600",
    },
    {
        "city": "Kolkata",
        "state": "West Bengal",
        "lat": 22.5726,
        "lon": 88.3639,
        "pincode_prefix": "700",
    },
    {
        "city": "Pune",
        "state": "Maharashtra",
        "lat": 18.5204,
        "lon": 73.8567,
        "pincode_prefix": "411",
    },
    {
        "city": "Ahmedabad",
        "state": "Gujarat",
        "lat": 23.0225,
        "lon": 72.5714,
        "pincode_prefix": "380",
    },
    {
        "city": "Jaipur",
        "state": "Rajasthan",
        "lat": 26.9124,
        "lon": 75.7873,
        "pincode_prefix": "302",
    },
    {
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "lat": 26.8467,
        "lon": 80.9462,
        "pincode_prefix": "226",
    },
]

BANK_IFSC_PREFIXES: list[str] = [
    "SBIN",
    "HDFC",
    "ICIC",
    "AXIS",
    "PUNB",
    "BARB",
    "KKBK",
    "YESB",
]

MCC_CATALOG: list[MccInfo] = [
    {"mcc": "5411", "category": "Grocery Stores", "risk": "LOW"},
    {"mcc": "5812", "category": "Eating Places & Restaurants", "risk": "LOW"},
    {"mcc": "5311", "category": "Department Stores", "risk": "LOW"},
    {"mcc": "4121", "category": "Taxicabs & Rideshares", "risk": "LOW"},
    {"mcc": "5732", "category": "Electronic Sales", "risk": "MEDIUM"},
    {"mcc": "4829", "category": "Wire Transfer & Money Orders", "risk": "HIGH"},
    {"mcc": "6051", "category": "Crypto & Quasi Cash", "risk": "CRITICAL"},
    {"mcc": "7995", "category": "Gambling & Betting", "risk": "CRITICAL"},
]


class FinancialDataGenerator:
    """
    Main generator for synthetic Indian banking data.
    """

    def __init__(
        self,
        seed: int = 42,
        dirty_rate: float = 0.03,
        fraud_rate: float = 0.015,
    ):
        self.seed = seed
        self.dirty_rate = dirty_rate
        self.fraud_rate = fraud_rate

        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)

        self.customers: list[Customer] = []
        self.accounts: list[Account] = []
        self.merchants: list[Merchant] = []
        self.transactions: list[Transaction] = []

    def _seeded_uuid(self) -> str:
        """Generates a reproducible UUID4 using the seeded RNG."""
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def generate_pan(self, is_valid: bool = True) -> str:
        """
        Generates an Indian PAN (Permanent Account Number).
        Format: 5 letters (4th letter 'P' for individual) + 4 digits + 1 letter.
        """
        if not is_valid:
            corruption_type = self.rng.choice(
                ["short", "chars", "no_digits", "lowercase"]
            )
            if corruption_type == "short":
                return "".join(self.rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
            elif corruption_type == "no_digits":
                return "ABCDEFGHIJ"
            elif corruption_type == "lowercase":
                return "abcde1234f"
            return "PAN9999XYZ"

        letters1 = "".join(self.rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
        entity_type = "P"  # Individual
        letter2 = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        digits = f"{self.rng.randint(1000, 9999):04d}"
        check_letter = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return f"{letters1}{entity_type}{letter2}{digits}{check_letter}"

    def generate_phone(self, is_valid: bool = True) -> str:
        """
        Generates an Indian mobile phone number (10 digits starting with 6, 7, 8, or 9).
        """
        if not is_valid:
            return self.rng.choice(
                ["98765", "1234567890123", "98765ABCD", "0000000000"]
            )
        prefix = self.rng.choice(["6", "7", "8", "9"])
        suffix = "".join([str(self.rng.randint(0, 9)) for _ in range(9)])
        return f"+91{prefix}{suffix}"

    def generate_synthetic_aadhaar(self) -> str:
        """
        Generates a 12-digit ID that is mathematically guaranteed to FAIL Verhoeff checksum.
        """
        prefix_11 = "".join([str(self.rng.randint(0, 9)) for _ in range(11)])
        return generate_invalid_verhoeff_12_digit(prefix_11)

    def generate_customers(self, count: int = 1000) -> list[Customer]:
        """
        Generates synthetic customer records.
        """
        customers: list[Customer] = []
        now = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

        for _ in range(count):
            cust_id = self._seeded_uuid()
            city_info = self.rng.choice(INDIAN_CITIES)
            created_date = now - timedelta(days=self.rng.randint(90, 730))
            dob = created_date - timedelta(
                days=self.rng.randint(6570, 25550)
            )  # 18-70 years old

            is_dirty = self.rng.random() < self.dirty_rate
            pan = self.generate_pan(is_valid=not (is_dirty and self.rng.random() < 0.5))
            phone = self.generate_phone(
                is_valid=not (is_dirty and self.rng.random() < 0.5)
            )
            email = (
                None if (is_dirty and self.rng.random() < 0.3) else self.fake.email()
            )

            pincode = f"{city_info['pincode_prefix']}{self.rng.randint(100, 999):03d}"
            kyc_status = self.rng.choices(
                ["VERIFIED", "PENDING", "REJECTED"], weights=[0.85, 0.12, 0.03]
            )[0]

            customer = Customer(
                customer_id=cust_id,
                full_name=self.fake.name(),
                email=email,
                phone=phone,
                pan=pan,
                aadhaar_id=self.generate_synthetic_aadhaar(),
                date_of_birth=dob.strftime("%Y-%m-%d"),
                address=self.fake.street_address().replace("\n", ", "),
                city=city_info["city"],
                state=city_info["state"],
                pincode=pincode,
                kyc_status=kyc_status,
                created_at=created_date.isoformat(),
                updated_at=created_date.isoformat(),
            )
            customers.append(customer)

        self.customers = customers
        return customers

    def generate_customer_updates(self, update_ratio: float = 0.05) -> list[Customer]:
        """
        Generates SCD Type 2 friendly updates for existing customers.
        Changes address, city, pincode, or transitions KYC from PENDING -> VERIFIED.
        """
        if not self.customers:
            raise ValueError("Generate customers first before creating updates")

        updates: list[Customer] = []
        now = datetime(2026, 11, 7, 0, 0, 0, tzinfo=timezone.utc)
        target_count = max(1, int(len(self.customers) * update_ratio))
        selected_customers = self.rng.sample(self.customers, target_count)

        for cust in selected_customers:
            new_city_info = self.rng.choice(
                [c for c in INDIAN_CITIES if c["city"] != cust.city]
            )
            new_pincode = (
                f"{new_city_info['pincode_prefix']}{self.rng.randint(100, 999):03d}"
            )
            new_kyc = "VERIFIED" if cust.kyc_status == "PENDING" else cust.kyc_status

            updated_cust = Customer(
                customer_id=cust.customer_id,
                full_name=cust.full_name,
                email=cust.email,
                phone=cust.phone,
                pan=cust.pan,
                aadhaar_id=cust.aadhaar_id,
                date_of_birth=cust.date_of_birth,
                address=f"Flat {self.rng.randint(101, 909)}, New Residency Road",
                city=new_city_info["city"],
                state=new_city_info["state"],
                pincode=new_pincode,
                kyc_status=new_kyc,
                created_at=cust.created_at,
                updated_at=(now - timedelta(days=self.rng.randint(1, 30))).isoformat(),
            )
            updates.append(updated_cust)

        return updates

    def generate_accounts(self, accounts_per_customer: float = 1.2) -> list[Account]:
        """
        Generates banking accounts linked to existing customers.
        """
        if not self.customers:
            raise ValueError("Generate customers first before creating accounts")

        accounts: list[Account] = []
        total_accounts = int(len(self.customers) * accounts_per_customer)

        for i in range(total_accounts):
            cust = self.customers[i % len(self.customers)]
            bank_prefix = self.rng.choice(BANK_IFSC_PREFIXES)
            ifsc = f"{bank_prefix}0{self.rng.randint(100000, 999999):06d}"
            acc_num = f"{self.rng.randint(10000000000, 999999999999):012d}"
            acc_type = self.rng.choices(
                ["SAVINGS", "CURRENT", "SALARY"], weights=[0.7, 0.15, 0.15]
            )[0]
            open_date = datetime.fromisoformat(cust.created_at) + timedelta(
                days=self.rng.randint(0, 10)
            )
            balance = round(float(self.np_rng.exponential(scale=35000) + 1500), 2)

            account = Account(
                account_id=self._seeded_uuid(),
                customer_id=cust.customer_id,
                account_number=acc_num,
                ifsc=ifsc,
                account_type=acc_type,
                open_date=open_date.strftime("%Y-%m-%d"),
                status=self.rng.choices(
                    ["ACTIVE", "DORMANT", "FROZEN"], weights=[0.95, 0.04, 0.01]
                )[0],
                balance=balance,
            )
            accounts.append(account)

        self.accounts = accounts
        return accounts

    def generate_merchants(self, count: int = 150) -> list[Merchant]:
        """
        Generates synthetic merchants with MCC codes and risk tiers.
        """
        merchants: list[Merchant] = []
        for i in range(count):
            mcc = self.rng.choice(MCC_CATALOG)
            city_info = self.rng.choice(INDIAN_CITIES)
            merchant_id = f"MERCH_{i + 1:05d}"
            name = f"{self.fake.company()} {mcc['category'].split()[0]}"

            merchant = Merchant(
                merchant_id=merchant_id,
                name=name,
                mcc_code=mcc["mcc"],
                city=city_info["city"],
                risk_tier=mcc["risk"],
            )
            merchants.append(merchant)

        self.merchants = merchants
        return merchants

    def generate_transactions(self, count: int = 5000) -> list[Transaction]:
        """
        Generates synthetic financial transactions including:
        - Realistic regular banking payments.
        - 1-2% complex financial fraud patterns.
        - Configurable dirty data injection (nulls, late arrivals, schema drift).
        """
        if not self.accounts or not self.merchants:
            raise ValueError(
                "Accounts and merchants must be generated before transactions"
            )

        transactions: list[Transaction] = []
        now = datetime(2026, 11, 7, 0, 0, 0, tzinfo=timezone.utc)
        fraud_target_count = int(count * self.fraud_rate)
        regular_count = count - fraud_target_count

        cust_by_id = {c.customer_id: c for c in self.customers}
        city_lookup: dict[str, CityInfo] = {c["city"]: c for c in INDIAN_CITIES}

        # ----------------------------------------------------
        # 1. Regular Transactions
        # ----------------------------------------------------
        for _ in range(regular_count):
            account = self.rng.choice(self.accounts)
            merchant = self.rng.choice(self.merchants)
            channel = self.rng.choices(
                ["UPI", "CARD", "NEFT", "IMPS", "ATM"],
                weights=[0.55, 0.25, 0.10, 0.07, 0.03],
            )[0]

            amount = round(float(self.np_rng.lognormal(mean=6.5, sigma=1.2)), 2)
            amount = max(10.0, min(amount, 200000.0))

            days_ago = self.rng.uniform(0, 30)
            txn_time = now - timedelta(days=days_ago)

            cust = cust_by_id.get(account.customer_id)
            home_city = (
                city_lookup.get(cust.city, INDIAN_CITIES[0])
                if cust
                else INDIAN_CITIES[0]
            )
            lat = home_city["lat"] + self.rng.uniform(-0.08, 0.08)
            lon = home_city["lon"] + self.rng.uniform(-0.08, 0.08)

            device_id: str | None = (
                f"dev_{account.customer_id[:8]}_{self.rng.randint(1, 2)}"
            )
            ip_address = self.fake.ipv4()

            is_dirty = self.rng.random() < self.dirty_rate
            if is_dirty:
                dirty_type = self.rng.choice(
                    ["null_device", "late_arrival", "schema_drift"]
                )
                if dirty_type == "null_device":
                    device_id = None
                elif dirty_type == "late_arrival":
                    txn_time = txn_time - timedelta(days=self.rng.randint(5, 14))

            promo = "PROMO2026" if (is_dirty and self.rng.random() < 0.2) else None

            txn = Transaction(
                txn_id=self._seeded_uuid(),
                account_id=account.account_id,
                merchant_id=merchant.merchant_id,
                amount=amount,
                currency="INR",
                channel=channel,
                txn_ts=txn_time.isoformat(),
                device_id=device_id,
                ip_address=ip_address,
                lat=round(lat, 4),
                lon=round(lon, 4),
                status=self.rng.choices(
                    ["SUCCESS", "PENDING", "FAILED"], weights=[0.94, 0.04, 0.02]
                )[0],
                is_fraud=0,
                fraud_pattern=None,
                promo_code=promo,
            )
            transactions.append(txn)

        # ----------------------------------------------------
        # 2. Fraud Patterns Injection (~1-2%)
        # ----------------------------------------------------
        fraud_patterns = [
            "velocity_burst",
            "impossible_travel",
            "high_value_night",
            "new_device_high_amount",
            "merchant_risk_spike",
            "card_testing_micro",
        ]

        remaining_fraud = fraud_target_count
        while remaining_fraud > 0:
            pattern = self.rng.choice(fraud_patterns)
            account = self.rng.choice(self.accounts)
            base_time = now - timedelta(days=self.rng.uniform(0.5, 25))

            if pattern == "velocity_burst":
                burst_size = min(4, remaining_fraud)
                for step in range(burst_size):
                    m = self.rng.choice(self.merchants)
                    step_time = base_time + timedelta(seconds=step * 20)
                    transactions.append(
                        Transaction(
                            txn_id=self._seeded_uuid(),
                            account_id=account.account_id,
                            merchant_id=m.merchant_id,
                            amount=round(self.rng.uniform(8000, 25000), 2),
                            channel="UPI",
                            txn_ts=step_time.isoformat(),
                            device_id=f"dev_fraud_{account.account_id[:6]}",
                            ip_address=self.fake.ipv4(),
                            lat=19.0760,
                            lon=72.8777,
                            status="SUCCESS",
                            is_fraud=1,
                            fraud_pattern="velocity_burst",
                        )
                    )
                remaining_fraud -= burst_size

            elif pattern == "impossible_travel":
                if remaining_fraud >= 2:
                    t1_time = base_time
                    t2_time = base_time + timedelta(minutes=15)
                    transactions.append(
                        Transaction(
                            txn_id=self._seeded_uuid(),
                            account_id=account.account_id,
                            merchant_id=self.rng.choice(self.merchants).merchant_id,
                            amount=round(self.rng.uniform(5000, 15000), 2),
                            channel="CARD",
                            txn_ts=t1_time.isoformat(),
                            device_id="dev_mumbai_01",
                            ip_address="103.21.124.10",
                            lat=19.0760,
                            lon=72.8777,
                            status="SUCCESS",
                            is_fraud=1,
                            fraud_pattern="impossible_travel",
                        )
                    )
                    transactions.append(
                        Transaction(
                            txn_id=self._seeded_uuid(),
                            account_id=account.account_id,
                            merchant_id=self.rng.choice(self.merchants).merchant_id,
                            amount=round(self.rng.uniform(35000, 80000), 2),
                            channel="CARD",
                            txn_ts=t2_time.isoformat(),
                            device_id="dev_delhi_02",
                            ip_address="49.36.120.45",
                            lat=28.7041,
                            lon=77.1025,
                            status="SUCCESS",
                            is_fraud=1,
                            fraud_pattern="impossible_travel",
                        )
                    )
                    remaining_fraud -= 2
                else:
                    remaining_fraud -= 1

            elif pattern == "high_value_night":
                night_time = base_time.replace(
                    hour=2, minute=30, second=self.rng.randint(0, 59)
                )
                transactions.append(
                    Transaction(
                        txn_id=self._seeded_uuid(),
                        account_id=account.account_id,
                        merchant_id=self.rng.choice(self.merchants).merchant_id,
                        amount=round(self.rng.uniform(85000, 350000), 2),
                        channel="IMPS",
                        txn_ts=night_time.isoformat(),
                        device_id=f"dev_night_{account.account_id[:4]}",
                        ip_address=self.fake.ipv4(),
                        lat=12.9716,
                        lon=77.5946,
                        status="SUCCESS",
                        is_fraud=1,
                        fraud_pattern="high_value_night",
                    )
                )
                remaining_fraud -= 1

            elif pattern == "new_device_high_amount":
                transactions.append(
                    Transaction(
                        txn_id=self._seeded_uuid(),
                        account_id=account.account_id,
                        merchant_id=self.rng.choice(self.merchants).merchant_id,
                        amount=round(self.rng.uniform(120000, 480000), 2),
                        channel="NEFT",
                        txn_ts=base_time.isoformat(),
                        device_id=f"brand_new_dev_{self._seeded_uuid()[:8]}",
                        ip_address=self.fake.ipv4(),
                        lat=17.3850,
                        lon=78.4867,
                        status="SUCCESS",
                        is_fraud=1,
                        fraud_pattern="new_device_high_amount",
                    )
                )
                remaining_fraud -= 1

            elif pattern == "merchant_risk_spike":
                high_risk_merchants = [
                    m for m in self.merchants if m.risk_tier == "CRITICAL"
                ]
                m = (
                    self.rng.choice(high_risk_merchants)
                    if high_risk_merchants
                    else self.rng.choice(self.merchants)
                )
                transactions.append(
                    Transaction(
                        txn_id=self._seeded_uuid(),
                        account_id=account.account_id,
                        merchant_id=m.merchant_id,
                        amount=round(self.rng.uniform(40000, 150000), 2),
                        channel="UPI",
                        txn_ts=base_time.isoformat(),
                        device_id=f"dev_{account.account_id[:6]}",
                        ip_address=self.fake.ipv4(),
                        lat=22.5726,
                        lon=88.3639,
                        status="SUCCESS",
                        is_fraud=1,
                        fraud_pattern="merchant_risk_spike",
                    )
                )
                remaining_fraud -= 1

            elif pattern == "card_testing_micro":
                items = min(4, remaining_fraud)
                for step in range(items - 1):
                    transactions.append(
                        Transaction(
                            txn_id=self._seeded_uuid(),
                            account_id=account.account_id,
                            merchant_id=self.rng.choice(self.merchants).merchant_id,
                            amount=round(self.rng.choice([1.0, 2.0, 5.0]), 2),
                            channel="CARD",
                            txn_ts=(
                                base_time + timedelta(seconds=step * 15)
                            ).isoformat(),
                            device_id="dev_tester_bot",
                            ip_address=self.fake.ipv4(),
                            lat=26.9124,
                            lon=75.7873,
                            status="SUCCESS",
                            is_fraud=1,
                            fraud_pattern="card_testing_micro",
                        )
                    )
                transactions.append(
                    Transaction(
                        txn_id=self._seeded_uuid(),
                        account_id=account.account_id,
                        merchant_id=self.rng.choice(self.merchants).merchant_id,
                        amount=round(self.rng.uniform(70000, 150000), 2),
                        channel="CARD",
                        txn_ts=(
                            base_time + timedelta(seconds=(items - 1) * 20)
                        ).isoformat(),
                        device_id="dev_tester_bot",
                        ip_address=self.fake.ipv4(),
                        lat=26.9124,
                        lon=75.7873,
                        status="SUCCESS",
                        is_fraud=1,
                        fraud_pattern="card_testing_micro",
                    )
                )
                remaining_fraud -= items

        self.rng.shuffle(transactions)

        if self.dirty_rate > 0:
            dup_count = int(len(transactions) * (self.dirty_rate / 3))
            if dup_count > 0:
                duplicates = self.rng.sample(transactions, dup_count)
                transactions.extend(duplicates)

        self.transactions = transactions
        return transactions
