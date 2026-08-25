# LinguaChat Design Implementation Guide

This is the concise implementation companion to the root `DESIGN.md`. It
describes how the current code maps to the contract; it is not a second design
system.

## Current surfaces

| Surface | Route | Entry component |
| --- | --- | --- |
| Login | `/login` | `features/auth/components/LoginForm` |
| Register | `/register` | `features/auth/components/RegisterForm` |
| Password recovery | `/forgot-password` | `features/auth/components/PasswordRecoveryForm` |
| Messaging | `/chat` | `features/chat/components/MessagingApp` |

## Layout model

Desktop uses a conversation ledger beside an edge-to-edge reading canvas. The
ledger owns search, filters, conversations and the signed-in account. The canvas
owns identity, message chronology and a compact docked composer. On mobile the
ledger and canvas become a list-to-conversation stack.

## Message rules

Messages are rendered as speaker blocks grouped by consecutive sender. The first
message in a day receives the date separator; timestamps remain subordinate and
outgoing timestamps align to the message edge. Delivery, edited, deleted, failed,
file and typing states use labels/icons in addition to color.

## Auth rules

The browser stores access/refresh session data through `shared/lib/auth-session`.
Login and registration call the backend API. A refresh token is rotated on
restore; invalid sessions are cleared and `/chat` redirects to `/login`.
Password reset is available at `/forgot-password`.

## File and group interactions

The attachment control is the native ChatScope attachment button wired to the
hidden file input. A selected file displays name, type, size, progress, cancel
and send actions. The group button opens a modal; users can search, select
members, name the group, submit, cancel or close with Escape.

## QA checklist

- `npm run build`
- `npx tsc --noEmit`
- backend auth tests
- keyboard path through login, registration, chat search, attachment and group modal
- 320px, 768px and wide desktop layouts
- long message/file names and empty conversation state
- offline/reconnecting/error states
- no accidental changes to hook/log files
