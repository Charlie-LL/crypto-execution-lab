from observer.stream import MarketObserver

def main():
    obs = MarketObserver()
    obs.start()

if __name__ == "__main__":
    main()