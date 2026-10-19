package benchmark;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class IoVerificationTest {
    @Test
    void standardCrcVectorAndRepeatability() {
        byte[] object = "123456789".getBytes(StandardCharsets.US_ASCII);
        var result = IoVerification.process(object);
        assertEquals(new Models.Response(null, "crc32:cbf43926", "OK", 9L), result);
        assertEquals(result, IoVerification.process(object));
        object[8] = '0';
        assertNotEquals(result.checksum(), IoVerification.process(object).checksum());
    }

    @Test
    void checkedInObjectHasExpectedByteCountAndChecksum() throws Exception {
        byte[] object = Files.readAllBytes(Path.of("../sample/dataset.json"));
        assertEquals(new Models.Response(null, "crc32:1c396adb", "OK", 191961L),
                IoVerification.process(object));
    }

    @Test
    void emptyObjectIsValidAndDeterministic() {
        assertEquals(new Models.Response(null, "crc32:00000000", "OK", 0L),
                IoVerification.process(new byte[0]));
    }
}
