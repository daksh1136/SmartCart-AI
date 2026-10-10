# SmartCart AI — Intelligent Scan & Go with Loss Prevention

**Tagline:** Scan. Verify. Go.

## Problem statement

Mobile scan-and-go retail reduces checkout friction, but there is a trust gap between products physically removed from shelves and products shoppers register on their phones. Accidental missed scans, incorrect quantities, and unverified picks make truly frictionless checkout difficult.

## Proposed solution

**SmartCart AI** maintains two independently updated carts: a physical cart derived from shelf pickup/return events, and a digital cart derived from barcode scans. A FastAPI reconciliation engine checks them in real time, makes discrepancies visible, and permits simulated checkout only when they match and any pending sensor evidence is resolved. Our prototype supports fixed camera zones with OpenCV, a simulated shelf-weight signal that can confirm camera events, a React customer interface, and a live operator dashboard. Uncertain signals are held for review rather than treated as evidence of theft.

## What is demonstrable today

- One shopper; three products in fixed shelf zones
- Barcode/manual scan and real-time quantity comparison
- Manual pickup simulation, plus optional calibrated webcam observation
- Optional **simulated** camera-and-weight evidence pairing
- Warning when a customer tries to exit with unscanned items
- Mock receipt generation only for a verified cart; duplicate attempts reuse the same receipt
- Backend acceptance tests covering the controlled scenarios

## Core technology

React/Vite, ZXing, Python FastAPI, OpenCV, SQLite, Web APIs. Optional YOLO tracking is a diagnostic overlay, not a SKU or theft classifier.

## What comes next

Real sensors (ESP32/HX711/load cells), product-specific camera training and validation, privacy-preserving multi-shopper event association, authentication, auditability, payment consent and production resilience.

> **Prototype disclaimer:** No actual payments, real shelf-weight hardware, or reliable shop-wide item attribution are claimed. This system is designed to demonstrate a verifiable workflow, not to determine criminal intent.
