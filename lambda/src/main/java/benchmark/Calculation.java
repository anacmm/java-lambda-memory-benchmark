package benchmark;

import java.util.List;
import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class Calculation {
    // Fixed work per record. Never derive this from Lambda memory or request parameters.
    public static final int ROUNDS = 8192;
    private static final long SEED = 0x6a09e667f3bcc909L;
    private static final long MULTIPLIER = 0x9e3779b97f4a7c15L;

    public Models.Response process(List<Models.DataRecord> records) {
        if (records == null) throw new IllegalArgumentException("Dataset records are required");
        long checksum = SEED;
        for (Models.DataRecord record : records) {
            if (record == null || record.category() == null) {
                throw new IllegalArgumentException("Every record requires a category");
            }
            long value = record.id() ^ Long.rotateLeft(record.value(), 17) ^ record.category().hashCode();
            for (int round = 0; round < ROUNDS; round++) {
                value = Long.rotateLeft(value ^ (value >>> 29), 13) * MULTIPLIER + round;
            }
            checksum = Long.rotateLeft(checksum ^ value, 7) * MULTIPLIER;
        }
        // Java long overflow is intentional and deterministic, including in the native executable.
        return new Models.Response(records.size(), Long.toUnsignedString(checksum, 16), "OK");
    }
}
