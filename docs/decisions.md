# Decisions

Log the decisions that actually shaped this codebase — the ones where a real alternative existed and
you picked one. At least five entries. For each: what you chose, what you rejected, and why. At least
one entry must be a decision you later reversed — say what changed your mind. It can be any entry
below, not necessarily the last one; add a **Later reversed:** line to whichever one it is.

## Decision 1

- **Chose:**
Django 6.1

- **Rejected:**
Older releases

- **Why:**
Django 6.1 was the latest release, so I assumed it would have the latest features and better support.

**Later Reversed.**

- **Chose:**
Django 5.1.15

- **Rejected:**
Django 6.1

- **Why:**
Django 5.1 is an LTS version, meaning it provides long-term stability and security support. This makes it more suitable for my application, especially since stability and long-term support are more important to me than having the latest features.

Django 5.1 will receive support until April 2028, whereas Django 6.1 is a newer release with a shorter support period. For this project, using a stable and well-supported version is more important than using the newest version, as the newer features do not provide any significant benefit for building a secure and functional application.

This decision was reversed because I initially installed Django 6.1 under the assumption that the latest version would provide newer and better features. However, I later realized that this project prioritizes stability, security, and long-term support over access to the newest features.

**Later Reversed again**

- **Chose:**
Django 5.2.17

- **Rejected:**
Django 5.1.15

- **Why:**
Django 5.1 does not support Python 3.14, which is the latest stable Python release. Downgrading Python does not seem sensible, so I decided to use a newer Django version instead.
I also found that Django 5.2 is the latest LTS release, so I switched to Django 5.2.17 for better long-term support and compatibility with Python 3.14.

## Decision 2

- **Chose:**
Django's built-in Session Authentication

- **Rejected:**
JWT Authentication and other token-based authentication methods

- **Why:**
Django's built-in session authentication is more suitable for this application because it is primarily a Django web application and does not currently require a stateless API authentication architecture.

JWT authentication is particularly useful for APIs and applications where stateless authentication is desirable, such as applications with separate frontend and backend services or mobile clients. Since this application is being built primarily with Django, introducing JWT would add additional complexity without providing a significant benefit for the current requirements.

Django's session-based authentication integrates directly with its built-in authentication and session frameworks. It also works with Django's built-in security mechanisms, including CSRF protection and security-related cookie settings such as `HttpOnly`, `Secure`, and `SameSite`. When these mechanisms are configured correctly and the application is deployed securely over HTTPS, session-based authentication provides a strong and appropriate security model for this application.

Therefore, I chose Django's built-in session authentication instead of introducing JWT or another token-based authentication system.

## Decision 3

- **Chose:**
- **Rejected:**
- **Why:**

## Decision 4

- **Chose:**
- **Rejected:**
- **Why:**

## Decision 5

- **Chose:**
- **Rejected:**
- **Why:**
