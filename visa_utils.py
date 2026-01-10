import pyvisa

def discover_and_connect(device_class_map):
    """
    Discovers, connects to, and initializes specified GPIB devices.

    Args:
        device_class_map: A dictionary where keys are device ID strings
                          (e.g., '8593EM') and values are the corresponding
                          wrapper classes (e.g., HP8593EM).

    Returns:
        A dictionary of initialized device objects, keyed by their device ID string.

    Raises:
        ConnectionError: If not all specified devices are found.
    """
    rm = pyvisa.ResourceManager()
    resources = [r for r in rm.list_resources() if r.startswith("GPIB")]
    print(f"Searching for {list(device_class_map.keys())} in GPIB resources: {resources}")

    found_devices = {}
    opened_resources = []

    device_ids_to_find = list(device_class_map.keys())

    try:
        for resource_str in resources:
            if len(found_devices) == len(device_ids_to_find):
                break

            try:
                resource = rm.open_resource(resource_str)
                opened_resources.append(resource)
                identity = resource.query("ID?").strip()

                for device_id, device_class in device_class_map.items():
                    if device_id in identity and device_id not in found_devices:
                        print(f"Found {device_id} at {resource_str}")
                        # Initialize the class with the resource
                        found_devices[device_id] = device_class(resource)
                        break 
            except pyvisa.errors.VisaIOError:
                continue # Ignore devices that can't be queried

        # Verify all devices were found
        for device_id in device_ids_to_find:
            if device_id not in found_devices:
                raise ConnectionError(f"Could not find device '{device_id}'.")

        # Close unused resources that were successfully opened
        all_instantiated_resources = [dev.resource for dev in found_devices.values()]
        for res in opened_resources:
            if res not in all_instantiated_resources:
                res.close()

        return found_devices

    except Exception:
        # Ensure all opened resources are closed on failure
        for res in opened_resources:
            try:
                # This might fail if the resource is already gone, but it's worth trying
                res.close()
            except pyvisa.errors.VisaIOError:
                pass 
        raise
