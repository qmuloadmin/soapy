# soapy

Simple, Intuitive SOAP library for consuming web services. Written in Python, for Python.

## Dependencies

..* CPython (or compatible) 3.0 or greater
..* BeautifulSoup 4
..* lxml

## Overview

Soapy is a library for making SOAP web service calls when given a WSDL. The goal of soapy is to create an extremely high-level web service client (no server) that is highly pythonic, simple and sufficient.

Sufficient is an important adjective for soapy, as I have no intentions of soapy being powerful (except possibly through simplicity). For instance, soapy will do absolutely zero type validation. Soapy's client will identify the possible input elements and attributes, provide a simple object for editing these items, and then marshal them into a correctly structured XML request. Concepts such as sequences and other structure components will be maintained, but if you pass in a string where an integer is expected, soapy will not complain, or even know, about the discrepancy.

This is partly because it's easier to ask forgiveness than permission, but also because, from a consumption standpoint, it is not substantially different if the client tells you your request is invalid by raising an error, or if the server raises a fault telling you the exact same thing. It's also because there are already numerous easy to use user clients for SOAP -- like SOAPUI that can detect these type errors easily. Soapy is not trying to replace the user interfaces, but simply provide an API, where the application using the API is already aware of the type constraints, but needs an API for forming the request.

## Motivation

I spent weeks working with Suds trying to make an interface with it that would easily integrate into my platform, to make general web service calls on limited information. Suds was no doubt powerful, but it's data structures were extremely difficult to follow as they relied heavily on factories and meta classes. Suds seemed more interested in making python SOAP-like than making SOAP pythonic. I finally managed to massage a solution that worked, until I ran into a bug that suds was not rendering attributes correctly in a particular WSDL, and after attempting to scour Suds' source to isolate the problem for hours, I decided I would be better served just making my own client to offer a far simpler API for programmatic consumption.

## Components

Soapy consists of three components:

..* Wsdl class

..* Marshaller class

..* Client class

