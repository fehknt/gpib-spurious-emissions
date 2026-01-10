import pyvisa

class HP8673B:
    def __init__(self, resource):
        self.resource = resource

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.resource.close()

    def identity(self):
        return self.resource.query("ID?").strip()

    def set_frequency(self, frequency_hz):
        self.resource.write(f"CW {int(frequency_hz)} HZ")

    def set_power(self, power_dbm):
        self.resource.write(f"PL {float(power_dbm):.2f} DB")

    def enable_rf(self, enabled: bool):
        if enabled:
            self.resource.write("RF1")
        else:
            self.resource.write("RF0")

if __name__ == '__main__':
    rm = pyvisa.ResourceManager()
    print(rm.list_resources())
    # Example usage:
    # gen = HP8673B(rm.open_resource('GPIB0::19::INSTR'))
    # print(gen.identity())
    # gen.set_frequency(1e9)
    # gen.set_power(0)
    # gen.enable_rf(True)
    # gen.close()
