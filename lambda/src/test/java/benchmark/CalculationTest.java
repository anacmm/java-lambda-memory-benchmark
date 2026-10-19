package benchmark;

import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CalculationTest {
    private final Calculation calculation = new Calculation();
    private final Models.DataRecord first = new Models.DataRecord(1, 7919, "group-1");
    private final Models.DataRecord second = new Models.DataRecord(2, 15838, "group-2");

    @Test
    void fixedVectorAndRepeatability() {
        var records = List.of(first, second);
        var result = calculation.process(records);
        assertEquals(2, result.recordsProcessed());
        assertEquals("OK", result.status());
        assertEquals("4951c005944415fe", result.checksum());
        assertEquals(result, calculation.process(records));
    }

    @Test
    void checksumDependsOnInputAndOrder() {
        var baseline = calculation.process(List.of(first, second));
        assertNotEquals(baseline.checksum(), calculation.process(List.of(second, first)).checksum());
        assertNotEquals(baseline.checksum(), calculation.process(List.of(first,
                new Models.DataRecord(2, 15839, "group-2"))).checksum());
        assertNotEquals(baseline.checksum(), calculation.process(List.of(first,
                new Models.DataRecord(2, 15838, "other"))).checksum());
    }

    @Test
    void emptyDatasetAndInvalidRecords() {
        assertEquals(new Models.Response(0, "6a09e667f3bcc909", "OK"), calculation.process(List.of()));
        assertThrows(IllegalArgumentException.class, () -> calculation.process(null));
        assertThrows(IllegalArgumentException.class,
                () -> calculation.process(List.of(new Models.DataRecord(1, 2, null))));
    }
}
