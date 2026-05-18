import re


class InjectionDetector:
    """
    A class to detect SQL injection, XSS, and Prompt Injection patterns.
    """

    def __init__(self):
        # Common patterns for SQL Injection
        # NOT NEED FOR NOW , BUT WILL BE USEFUL IN THE FUTURE
        self.sql_patterns = [
            re.compile(r"union\s+select", re.IGNORECASE),
            re.compile(r"drop\s+table", re.IGNORECASE),
            re.compile(r"insert\s+into", re.IGNORECASE),
            re.compile(r"--", re.IGNORECASE),
            re.compile(r";", re.IGNORECASE),
        ]
        # Common patterns for XSS
        # NOT NEED FOR NOW , BUT WILL BE USEFUL IN THE FUTURE
        self.xss_patterns = [
            re.compile(r"<script.*?>", re.IGNORECASE),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"onload=", re.IGNORECASE),
        ]
        # Common patterns for Prompt Injection
        self.prompt_injection_patterns = [
            re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
            re.compile(r"disregard\s+all\s+previous", re.IGNORECASE),
            re.compile(r"system\s+override", re.IGNORECASE),
            re.compile(r"new\s+rule:", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
            re.compile(r"forget\s+everything", re.IGNORECASE),
            re.compile(r"do\s+not\s+follow", re.IGNORECASE),
        ]

    def is_malicious(self, input_string: str) -> bool:
        """
        Checks if the input string contains known injection patterns.
        """
        if not input_string:
            return False

        # Check Prompt Injection
        for pattern in self.prompt_injection_patterns:
            if pattern.search(input_string):
                return True

        return False


# Creating a global instance to mimic the expected usage in your project
detector = InjectionDetector()


def detect_injection(input_string: str) -> bool:
    """
    Functional wrapper for the detector instance.
    """
    return detector.is_malicious(input_string)
