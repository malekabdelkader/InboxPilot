import re

class InjectionDetector:
    """
    A placeholder class to prevent ImportError.
    Currently detects basic SQL and XSS patterns.
    """
    def __init__(self):
        # Common patterns for SQL Injection
        self.sql_patterns = [
            re.compile(r"union\s+select", re.IGNORECASE),
            re.compile(r"drop\s+table", re.IGNORECASE),
            re.compile(r"insert\s+into", re.IGNORECASE),
            re.compile(r"--", re.IGNORECASE),
            re.compile(r";", re.IGNORECASE),
        ]
        # Common patterns for XSS
        self.xss_patterns = [
            re.compile(r"<script.*?>", re.IGNORECASE),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"onload=", re.IGNORECASE),
        ]

    def is_malicious(self, input_string: str) -> bool:
        """
        Checks if the input string contains known injection patterns.
        """
        if not input_string:
            return False

        # Check SQL Injection
        for pattern in self.sql_patterns:
            if pattern.search(input_string):
                return True

        # Check XSS
        for pattern in self.xss_patterns:
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
