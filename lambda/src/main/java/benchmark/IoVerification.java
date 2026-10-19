package benchmark;

import java.util.HexFormat;
import java.util.zip.CRC32;

/** One lightweight pass over the downloaded bytes; no JSON parsing or calculation rounds. */
public final class IoVerification {
    private IoVerification() {}

    public static Models.Response process(byte[] object) {
        CRC32 crc = new CRC32();
        crc.update(object);
        return new Models.Response(null, "crc32:" + HexFormat.of().toHexDigits((int) crc.getValue()),
                "OK", (long) object.length);
    }
}
