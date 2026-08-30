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
## Decision 2

- **Chose:**
- **Rejected:**
- **Why:**

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
